#!/bin/sh
# Does a melee hit on a creature behind an energy shield sound the weapon's forcefield column? From `uppercity`
# (kotor/tools/checkpoints/make.sh), with shield1.txt: a Sith trooper 2 m ahead with a forceshields.2da row 1 shield
# (`ui shield`), which the leader attacks with its blade. The original's hit sound (0x00617470) takes "forcefield" for
# a shielded creature before its sound set's or armour's material (docs/re/actions.md 3.15). FAIL and exit status 1
# unless every hit of the leader's on the trooper plays a weaponsounds.2da forcefield sound (cb_ht_*frce*), at least one.
#
#   sh kotor/tools/combat/hitsound.sh            (EXE=kotor/out/kotor.exe; run from the repository root; about 4 seconds)
#
# The log is kotor/out/combat/shield1.log.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${EXE:-kotor/out/kotor.exe}
out=kotor/out/combat
ck=kotor/out/checkpoints
mkdir -p $out
if [ ! -d $ck/uppercity ]; then echo "no checkpoint $ck/uppercity: run sh kotor/tools/checkpoints/make.sh first"; exit 2; fi
rm -rf $out/saves_shield1
$exe --load $ck/uppercity --no-render --speed 8 --saves $out/saves_shield1 --input kotor/tools/combat/shield1.txt --frames 600 --log combat,sound > $out/shield1.log 2>&1
log=$out/shield1.log
# The hit sound that follows each "TROOPER takes N damage from LEADER" line on the same tick.
res=$(awk '/ takes [0-9]+ damage from 2147483647/ { t = $1; want = 1; next }
           want && $1 == t && / sound play cb_ht_/ { if ($5 ~ /frce/) ok++; else bad++; want = 0 }
           END { print ok + 0, bad + 0 }' $log)
ok=${res% *}
bad=${res#* }
if [ "$ok" -lt 1 ] || [ "$bad" -gt 0 ]; then
  echo "FAIL $ok forcefield hit sounds, $bad others on the shielded trooper (see $log)"
  exit 1
fi
echo "ok   $ok hits on the shielded trooper, all forcefield"
