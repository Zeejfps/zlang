#!/bin/sh
# Door sounds (placeableobjsnds.2da; docs/re/actions.md 3.15), headless and quick (--no-render --speed 8):
#
#   EXE=kotor/out/kotor.exe [CK=kotor/out/checkpoints] [OUT=kotor/out/sndrun] sh kotor/tools/sndrun/doors.sh
#
# From the uppercity checkpoint the leader tries a locked apartment door (ptar_lockde), then bashes it open
# (doors.txt). FAIL (exit 1) unless `--log sound` shows the door's Locked sound, then its Opened sound.
# (The Endar Spire run of run.sh checks the footlocker's and the doors' open and close sounds.)
export PATH=/g/Dev/msys64/mingw64/bin:$PATH     # SDL2.dll
exe=${EXE:-kotor/out/kotor.exe}
ck=${CK:-kotor/out/checkpoints}
out=${OUT:-kotor/out/sndrun}
if [ ! -d $ck/uppercity ]; then echo "skip doors: no checkpoint $ck/uppercity (sh kotor/tools/checkpoints/make.sh)"; exit 0; fi
mkdir -p $out
rm -rf $out/saves_doors
timeout 600 $exe --no-render --speed 8 --load $ck/uppercity --saves $out/saves_doors --input kotor/tools/sndrun/doors.txt \
  --frames 1500 --log sound,objects > $out/doors.log 2>&1
locked=$(grep -a -c 'sound play dr_metal_lock row 22$' $out/doors.log)
# The bashed door's Opened comes after its state change (`door ID (ptar_lockde) -> 1|2`).
opened=$(grep -a -A3 '(ptar_lockde) -> [12]' $out/doors.log | grep -a -c 'sound play dr_.*_open row 22$')
echo "     doors: $locked locked, $opened opened (bashed)"
if [ "$locked" -gt 0 ] && [ "$opened" -gt 0 ]; then echo "ok   doors"; exit 0; fi
echo "FAIL doors: see $out/doors.log"
exit 1
