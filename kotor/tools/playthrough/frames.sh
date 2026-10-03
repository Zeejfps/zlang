#!/bin/sh
# Runs a script for each frame count given and says which ones hang (exit 124 after TIMEOUT seconds).
#
#   TIMEOUT=15 sh kotor/tools/playthrough/frames.sh SCRIPT N1 N2 ...
script=$1
shift
for n in "$@"; do
  r=$(TIMEOUT=${TIMEOUT:-15} LOG=none sh kotor/tools/playthrough/run.sh bisect "$script" "$n")
  echo "$n: $r"
done
