#!/bin/sh
# The light side the other way: Bastila is killed, not redeemed (docs/playthrough-star-forge.md). Part 8 is 08k_bastila_kill.txt; parts 9 to
# 11 are the chain's own, from checkpoints of this branch of the story (bastdead, gensk, fightk). Needs the checkpoint "freeze" of all.sh.
#
#   sh kotor/tools/playthrough/starforge/kill.sh        (about 10 minutes)
d=kotor/tools/playthrough/starforge
export LOG=${LOG:-dialog,combat}

echo "== part 8k from 'freeze' to 'bastdead'"
CKPT=freeze TIMEOUT=900 sh $d/run.sh s8k $d/08k_bastila_kill.txt 12500 12470:end
grep -a -F -q "dialog end k_sta_bastlast (aborted)" kotor/out/pt/s8k.log || { echo "FAIL part 8k: Bastila was not killed"; exit 1; }
sh $d/ckpt.sh bastdead
echo "== part 9 from 'bastdead' to 'gensk'"
CKPT=bastdead TIMEOUT=900 sh $d/run.sh s9k 09 10100 10070:end
grep -a -F -q "global STA_GENERATORS 6" kotor/out/pt/s9k.log || { echo "FAIL part 9"; exit 1; }
sh $d/ckpt.sh gensk
echo "== part 10 from 'gensk' to 'fightk'"
CKPT=gensk TIMEOUT=900 sh $d/run.sh s10k 10 4000 3970:end
grep -a -F -q "dialog end k_sta_darthmalak (normal)" kotor/out/pt/s10k.log || { echo "FAIL part 10"; exit 1; }
sh $d/ckpt.sh fightk
echo "== part 11 from 'fightk' (the films, the credits and the main menu shown)"
CKPT=fightk ARGS=--cinema TIMEOUT=1200 sh $d/run.sh s11k 11 40000 39970:end
grep -a -F -q "to the main menu" kotor/out/pt/s11k.log || { echo "FAIL part 11"; exit 1; }
echo "the Bastila-killed chain is done"
