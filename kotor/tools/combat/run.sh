#!/bin/sh
# Runs one combat test of docs/mechanics/combat.md from a checkpoint (kotor/tools/checkpoints/make.sh) and
# prints its combat lines:
#
#   sh kotor/tools/combat/run.sh CHECKPOINT TEST FRAMES [FRAME:SHOT]...
#
# TEST is kotor/tools/combat/TEST.txt; the log is kotor/out/combat/TEST.log, pictures TEST_SHOT.png.
# EXE (kotor/out/kotor.exe), LOG (combat), PAT (the lines printed: a grep -E pattern), N (how many).
#
#   feat1     uppercity  450   the target block's combat feats queued by clicks (Critical Strike, Flurry, Power Attack)
#   rapid1    uppercity  250   a blaster from 18 m: Power Blast / Rapid Shot in the block, two shots, no approach
#   retarget1 uppercity  850   three troopers: the leader turns on the next foe after each kill
#   down1     uppercity  400   Carth down (die1, dead1), the foe killed, Carth up 5 s later (getupdead1)
#   med1      uppercity  600   a wounded trooper uses its medpac (k_ai_master talents)
#   bash1     bunk       1000  a locked non-plot door bashed open through the block
#   gren2     bunk       600   Trask as grenadier (Scripts panel style 4) throws frag grenades
#   gren1     uppercity  130   Carth targeted (empty block), then a frag grenade thrown at a hostile trooper (checked by grenade.sh)
#   provoke1  uppercity  600   a dark Jedi turned hostile with a buff on itself as its first order attacks once the buff is cast
#   engage1   uppercity  620   paused after an enemy is sighted, the block's attack puts the leader in combat mode at once
#                              (checked by engage.sh)
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
cp=$1; name=$2; frames=$3; shift 3
mkdir -p kotor/out/combat
shots=""
for s in "$@"; do shots="$shots --screenshot-at ${s%%:*}:kotor/out/combat/${name}_${s#*:}.png"; done
rm -rf kotor/out/combat/saves_$name
${EXE:-kotor/out/kotor.exe} --load kotor/out/checkpoints/$cp --no-render --speed 8 --saves kotor/out/combat/saves_$name \
  --input kotor/tools/combat/$name.txt --frames $frames --log ${LOG:-combat} $shots > kotor/out/combat/$name.log 2>&1
echo "exit $? faults $(grep -a -c '^fault' kotor/out/combat/$name.log)"
grep -a -E "${PAT:-^fight|attacks [0-9]+:|dies|is down|gets up|turns on|casts}" kotor/out/combat/$name.log | head -${N:-60}
