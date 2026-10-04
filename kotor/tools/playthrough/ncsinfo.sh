#!/bin/sh
# What each script calls, in one line: sh kotor/tools/playthrough/ncsinfo.sh SCRIPT...
# (the disassembly kotor/out/ncs/SCRIPT.txt, made by ncsgrep.sh MODULE: routine names and string constants in order).
for s in "$@"; do
  echo "== $s: $(grep 'ACTION\|CONSTS' kotor/out/ncs/$s.txt 2>/dev/null | sed 's/^ *[0-9a-f]* *//' | tr -s ' ' | sed 's/ACTION [0-9]* [0-9]* ; //' | tr '\n' ';' | cut -c1-500)"
done
