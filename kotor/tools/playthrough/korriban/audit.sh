#!/bin/sh
# The staging audit of every part's log (kotor/tools/py/stage_audit.py): the conversations whose speakers stood more than 8 m apart (FAR) or
# in other rooms (ROOMS), per part: sh kotor/tools/playthrough/korriban/audit.sh [PART...]  (the parts of all.sh when none is given)
parts=${*:-"2 3 4 6 7 8 9 10 11 12 13 14 18 22 23 24 25 26 27 28 32"}
for p in $parts; do
  echo "== part $p"
  python kotor/tools/py/stage_audit.py kotor/out/pt/k$p.log 2>/dev/null | awk '/^[a-z]/ { head = $0; shown = 0; next } /FAR|ROOMS/ { if (!shown) { print head; shown = 1 } print $0 }'
done
