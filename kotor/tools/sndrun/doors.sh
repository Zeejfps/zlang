#!/bin/sh
# Door and placeable sounds (placeableobjsnds.2da; docs/re/actions.md 3.15), headless and quick (--no-render --speed 8):
#
#   EXE=kotor/out/kotor.exe [CK=kotor/out/checkpoints] [OUT=kotor/out/sndrun] sh kotor/tools/sndrun/doors.sh
#
# From the uppercity checkpoint (doors.txt) the leader tries a locked apartment door (ptar_lockde), then bashes
# it open; a second apartment door dies of EffectDeath; a Sith trooper carrying an item is killed, and its body
# bag opened and closed. FAIL (exit 1) unless the logs show:
#   locked   the door's Locked sound, feedback 1437 "This object is locked." and the text 1439 "Locked" over it
#   hits     the bashing blows sound weaponsounds.2da's metal column (the door's ArmorType)
#   opened   its Opened sound after the bash opened it
#   death    the second door destroyed (state 3) without opening, and gone 2 s (60 frames) later
#   corpse   the bag, its corpse still lying there, closing as placeableobjsnds row 53 (pl_corpse_close)
# (The Endar Spire run of run.sh checks the footlocker's and the doors' open and close sounds.)
export PATH=/g/Dev/msys64/mingw64/bin:$PATH     # SDL2.dll
exe=${EXE:-kotor/out/kotor.exe}
ck=${CK:-kotor/out/checkpoints}
out=${OUT:-kotor/out/sndrun}
if [ ! -d $ck/uppercity ]; then echo "skip doors: no checkpoint $ck/uppercity (sh kotor/tools/checkpoints/make.sh)"; exit 0; fi
mkdir -p $out
rm -rf $out/saves_doors
timeout 600 $exe --no-render --speed 8 --load $ck/uppercity --saves $out/saves_doors --input kotor/tools/sndrun/doors.txt \
  --frames 1800 --log sound,objects > $out/doors.log 2>&1
log=$out/doors.log
locked=$(grep -a -A1 'locked [0-9]*: feedback 1437, text 1439$' $log | grep -a -c 'sound play dr_metal_lock row 22$')
hits=$(grep -a -c 'sound play cb_ht_.*metal row 15$' $log)
# The bashed door's Opened comes after its state change (`door ID (ptar_lockde) -> 1|2`).
opened=$(grep -a -A3 '(ptar_lockde) -> [12]' $log | grep -a -c 'sound play dr_.*_open row 22$')
dead=$(grep -a '(ptar_lockde) -> 3$' $log | head -1 | sed 's/^\[\([0-9]*\) .*door \([0-9]*\) .*/\1 \2/')
death=0
if [ -n "$dead" ]; then
  set -- $dead
  gone=$(grep -a "destroy $2 ptar_lockde\$" $log | head -1 | sed 's/^\[\([0-9]*\) .*/\1/')
  reopened=$(grep -a -c "door $2 (ptar_lockde) -> [12]" $log)
  [ -n "$gone" ] && [ $((gone - $1)) -eq 60 ] && [ "$reopened" -eq 0 ] && death=1
fi
corpse=$(grep -a -c 'sound play pl_corpse_close row 22$' $log)
echo "     doors: $locked locked, $hits metal hits, $opened opened (bashed), death $death, $corpse corpse bag closed"
if [ "$locked" -gt 0 ] && [ "$hits" -gt 0 ] && [ "$opened" -gt 0 ] && [ "$death" -eq 1 ] && [ "$corpse" -gt 0 ]; then echo "ok   doors"; exit 0; fi
echo "FAIL doors: see $log"
exit 1
