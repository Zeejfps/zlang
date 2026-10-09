#!/bin/sh
# Does a container's lid open and close, and does an emptied one stay open? The Endar Spire's footlocker from a new
# game (kotor/tools/containers/locker.txt, --log objects,sound): FAIL and exit status 1 unless, in order,
#
#   open    the first use sounds pl_footlkr_open and plays close2open then open (the lid lifts before the panel)
#   close   Close plays open2close then close and sounds pl_footlkr_close
#   reopen  the second use opens it again (close2open, the open sound)
#   empty   Get Items leaves it open: no close animation or sound after it (ours, docs/mechanics/items-skills.md)
#   load    the save made then shows it open at once after the load ("plays open"), and using it again plays no
#           open sound
#
#   sh kotor/tools/containers/locker.sh        (EXE=kotor/out/kotor.exe; run from the repository root; about 5 s)
#
# The log is kotor/out/containers/locker.log. docs/re/actions.md 3.5 and 3.15 say what the original does.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${EXE:-kotor/out/kotor.exe}
out=kotor/out/containers
log=$out/locker.log
mkdir -p $out
rm -rf $out/saves
timeout ${TIMEOUT:-300} $exe --no-render --speed 8 --frames 3400 --input kotor/tools/containers/locker.txt \
  --saves $out/saves --log objects,sound > $log 2>&1
fail=0

# The footlocker's lines in order, one word each: open, close, opensnd, closesnd, shown (first seen open), save,
# load (the new game's own loading screen first).
seq=$(grep -a -E 'end_locker01 plays|sound play pl_footlkr_|\] saved |loading screen up' $log | awk '
  /plays close2open then open/ { printf "open " }
  /plays open2close then close/ { printf "close " }
  /plays open$/ { printf "shown " }
  /pl_footlkr_open/ { printf "opensnd " }
  /pl_footlkr_close/ { printf "closesnd " }
  /\] saved / { printf "save " }
  /loading screen up/ { printf "load " }')
echo "     sequence: $seq"
want="load opensnd open closesnd close opensnd open save load shown "
if [ "$seq" = "$want" ]; then
  echo "ok   locker: opens, closes, reopens, stays open when emptied and after a load, silent when used again"
else
  echo "FAIL locker: wanted \"$want\""; fail=1
fi
if ! grep -a -q '0 faults' $log; then echo "FAIL locker: script faults (see $log)"; fail=1; fi
exit $fail
