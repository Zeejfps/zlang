#!/bin/sh
# One picture per module, side by side: sh kotor/tools/playthrough/sweep.sh OUT.png MODULE...
# Each module loads headless (--no-render) for 400 frames with the player where the module puts him, and the picture of
# frame 380 goes into a contact sheet (3 per row) next to a line of what the run reported (faults, missing routines,
# textures). The sheet is kotor/out/pt/OUT.png; the logs are kotor/out/pt/sweep_MODULE.log.
out=$1
shift
mkdir -p kotor/out/pt
echo "" > kotor/out/pt/sweep_empty.txt
for m in "$@"; do
  FAST=1 sh kotor/tools/playthrough/run.sh sweep_$m kotor/out/pt/sweep_empty.txt 400 380:shot -- --module $m > /dev/null
  echo "$m: $(grep -a '^run:' kotor/out/pt/sweep_$m.log | cut -c1-120) | $(grep -a '^scene:' kotor/out/pt/sweep_$m.log | sed 's/scene: //' | cut -c1-90)"
done
python kotor/tools/py/contact_sheet.py kotor/out/pt/$out $(for m in "$@"; do echo kotor/out/pt/sweep_${m}_shot.png; done)
