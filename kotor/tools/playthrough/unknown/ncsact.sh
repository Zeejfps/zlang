#!/bin/sh
# The routine calls and string constants of disassembled scripts (kotor/out/ncs/NAME.txt, made by ncsall.sh / ncsgrep.sh), one script a line:
#   sh kotor/tools/playthrough/unknown/ncsact.sh k_punk_repair k_punk_goebon
# Run from the repository root.
for n in "$@"; do
  echo "== $n"
  grep -a "ACTION\|CONSTS\|CONSTI [0-9][0-9]*$" kotor/out/ncs/$n.txt | sed 's/^ *[0-9a-f]* *//' | tr -s ' ' | tr '\n' ';' | cut -c1-${WIDTH:-900}
  echo
done
