#!/bin/sh
# The sound modes 3, 4, 5 and 6 (docs/design/audio.md, "Sound modes"), headless with --log sound:
#
#   EXE=kotor/out/kotor.exe [CK=kotor/out/checkpoints] [OUT=kotor/out/sndrun] sh kotor/tools/sndrun/modes.sh
#
# From the uppercity checkpoint (modes.txt; the scripted `focus lost|gained` stands for the window's activation).
# FAIL (exit 1) unless the log's `sound mode N` lines run 5 6 4 5 0 6 3 0 and the first 5 and the save's 3 stopped
# sounds (the area's ambient bed and placed sounds play there).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH     # SDL2.dll
exe=${EXE:-kotor/out/kotor.exe}
ck=${CK:-kotor/out/checkpoints}
out=${OUT:-kotor/out/sndrun}
if [ ! -d $ck/uppercity ]; then echo "skip modes: no checkpoint $ck/uppercity (sh kotor/tools/checkpoints/make.sh)"; exit 0; fi
mkdir -p $out
rm -rf $out/modes_saves
$exe --load $ck/uppercity --headless --saves $out/modes_saves --input kotor/tools/sndrun/modes.txt --frames 100 --log sound > $out/modes.log 2>&1
modes=$(grep -a 'sound mode' $out/modes.log | sed -E 's/.*sound mode ([0-9]+):.*/\1/' | xargs)
first5=$(grep -a -m1 'sound mode 5:' $out/modes.log | sed -E 's/.*: ([0-9]+) sounds.*/\1/')
save3=$(grep -a -m1 'sound mode 3:' $out/modes.log | sed -E 's/.*: ([0-9]+) sounds.*/\1/')
if [ "$modes" != "5 6 4 5 0 6 3 0" ] || [ "${first5:-0}" -eq 0 ] || [ "${save3:-0}" -eq 0 ]; then
  echo "FAIL modes: [$modes] (want 5 6 4 5 0 6 3 0), held at the first 5: ${first5:-none}, at the save's 3: ${save3:-none} (see $out/modes.log)"
  exit 1
fi
echo "ok   modes: 5 6 4 5 0 6 3 0; $first5 sounds held when the window went, $save3 while the save was written"
