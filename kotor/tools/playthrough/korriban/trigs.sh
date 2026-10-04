#!/bin/sh
# The outlines (world coordinates) and enter scripts of triggers: sh kotor/tools/playthrough/korriban/trigs.sh MODULE TAG...
module=$1
shift
for t in "$@"; do
  echo "== $t"
  sh kotor/tools/playthrough/kashyyyk/trig.sh $module $t
done
