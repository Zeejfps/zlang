#!/bin/sh
# Two paths of the player's orders in a fight, from `uppercity` (kotor/tools/checkpoints/make.sh):
#
#   clicked  clicked1.txt: two Sith troopers; the leader fights the first, then (Q/E's next target and R, mid-round)
#            is ordered onto the second while it still fights the first. The attack input keeps the second as the
#            clicked target (+0x510) while the attempted target (+0x50c) stays the first until the leader attacks
#            the second, so the first's attacks on the leader run unpaired (GetCanEngage 0x004d2c30; --log combat:
#            "A not paired with 2147483647: its clicked target is B", A and B the troopers' ids). FAIL unless the fight
#            line right after R shows "attempted A clicked B" and the refusal is logged.
#   selfq    selfq1.txt: with the auto-pause on, a trooper appears (the game pauses), the target block's attack puts the
#            leader in combat mode, and a self slot (BTN_ACTION1, a medpac) is used: in combat mode during an
#            auto-pause the banner turns to "Action added to queue." (48423; UseSelfAction 0x0068ad60, reason 10).
#            FAIL unless the banner line follows the slot's click and the use (action 15) waits in the leader's queue
#            behind the attack (12): in combat mode a self slot queues (UseSelfAction, AddItemCastSpellActions 0x004f8c70).
#
#   sh kotor/tools/combat/clicked.sh            (EXE=kotor/out/kotor.exe; run from the repository root; about 10 seconds)
#
# Logs in kotor/out/combat/clicked1.log and selfq1.log. docs/re/combat.md (+0x510), docs/re/gui.md (UseSelfAction).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${EXE:-kotor/out/kotor.exe}
out=kotor/out/combat
ck=kotor/out/checkpoints
mkdir -p $out
if [ ! -d $ck/uppercity ]; then echo "no checkpoint $ck/uppercity: run sh kotor/tools/checkpoints/make.sh first"; exit 2; fi
fail=0

rm -rf $out/saves_clicked1
$exe --load $ck/uppercity --no-render --speed 8 --saves $out/saves_clicked1 --input kotor/tools/combat/clicked1.txt --frames 420 --log combat > $out/clicked1.log 2>&1
log=$out/clicked1.log
# The troopers' ids (the first is fought first, the second ordered next) depend on the checkpoint: from the spawn lines.
first=$(grep -a '^spawn g_sithtroop01' $log | sed -n 1p | awk '{ print $3 }')
second=$(grep -a '^spawn g_sithtroop01' $log | sed -n 2p | awk '{ print $3 }')
after=$(grep -a '^fight leader' $log | sed -n 2p | sed -E 's/.* (attempted [0-9]+ clicked [0-9]+) .*/\1/')
refused=$(grep -a -c -E "^\[[0-9]+ [0-9.]+\] $first not paired with 2147483647: its clicked target is $second" $log)
if [ "$after" != "attempted $first clicked $second" ] || [ "$refused" -lt 1 ]; then
  echo "FAIL clicked: after R '$after' (want 'attempted $first clicked $second'), $refused refusals logged (want 1 or more; see $log)"
  fail=1
else
  echo "ok   clicked: the order on $second kept as the clicked target, $first's attacks unpaired $refused times"
fi

rm -rf $out/saves_selfq1
$exe --load $ck/uppercity --no-render --speed 8 --saves $out/saves_selfq1 --input kotor/tools/combat/selfq1.txt --frames 100 --log combat,objects > $out/selfq1.log 2>&1
log=$out/selfq1.log
banner=$(grep -a -E '^\[[0-9]+ [0-9.]+\] pause banner: 48423' $log | head -1 | sed -E 's/^\[([0-9]+) .*/\1/')
queue=$(grep -a '^fight leader' $log | sed -n 4p | sed -E 's/.* queue (.*) waiting .*/\1/')
case "$queue" in *12:*15:*) used=1 ;; *) used=0 ;; esac
if [ -z "$banner" ] || [ "$banner" -lt 60 ] || [ $used = 0 ]; then
  echo "FAIL selfq: banner 48423 at tick '$banner' (want after the slot's click at 60), leader's queue '$queue' (want the attack, 12, then the use, 15; see $log)"
  fail=1
else
  echo "ok   selfq: the self slot in combat mode during the auto-pause turned the banner to 48423 (tick $banner), the use queued behind the attack"
fi
exit $fail
