#!/bin/sh
# Each party member's experience and the leader's alignment (0 dark .. 100 light) at checkpoints of the Unknown World chain
# (a short run from each):  sh kotor/tools/playthrough/unknown/xp.sh crash beach duros ...
# Run from the repository root.
for c in "$@"; do
  printf '%s\n' '3 ui xp' '3 ui rules' > kotor/out/pt/xp_probe.txt
  CKPT=$c LOG=dialog sh kotor/tools/playthrough/unknown/run.sh xp kotor/out/pt/xp_probe.txt 10 > /dev/null 2>&1
  echo "== $c: $(grep -a '^xp \|  align' kotor/out/pt/xp.log | tr '\n' ' ' | tr -s ' ')"
done
