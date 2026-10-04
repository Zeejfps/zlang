#!/bin/sh
# Loads each module headless for a few seconds and says what it printed: faults, errors, missing routines,
# textures. Pictures go to kotor/out/pt/smoke_MODULE.png.
#
#   sh kotor/tools/playthrough/smoke.sh tar_m02aa tar_m03aa ...        (FRAMES, default 150)
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
mkdir -p kotor/out/pt
for m in "$@"; do
  timeout ${TIMEOUT:-120} kotor/out/kotor.exe --module "$m" --headless --frames ${FRAMES:-150} --screenshot-at ${FRAMES:-150}:kotor/out/pt/smoke_$m.png --log none > kotor/out/pt/smoke_$m.log 2>&1
  rc=$?
  echo "$m: exit $rc; $(grep -a '^run:' kotor/out/pt/smoke_$m.log | sed 's/run: //') | $(grep -a '^routines called' kotor/out/pt/smoke_$m.log) | $(grep -a '^scene:' kotor/out/pt/smoke_$m.log | sed 's/scene: //' | cut -c1-90) $(grep -a -c 'kotor:' kotor/out/pt/smoke_$m.log) errors"
done
