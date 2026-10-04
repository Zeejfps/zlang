#!/bin/sh
# Do the companions fight? Three fights from checkpoints (kotor/tools/checkpoints/make.sh), each checked for the
# attack rounds a party member made in it, FAIL and exit status 1 when it made none:
#
#   sh kotor/tools/combat/companions.sh            (EXE=kotor/out/kotor.exe; run from the repository root; about a minute)
#
#   room3   bunk      Trask in the Endar Spire's room 3 (the cut scene k_pend_cut1_end clears his queue and orders him to
#                     attack two frames later; a FOLLOWLEADER queued in between kept him in the corridor)
#   bridge  bunk      Trask against the reinforcements before the bridge, with the player walking on by hand (the bot,
#                     whose leader kills them in a few rounds, is switched off before them)
#   carth   uppercity Carth beside the leader, three troopers 4 to 5 m ahead (combat/retarget1.txt)
#
# The logs are kotor/out/combat/companions_NAME.log (--log combat; `party` lines name the ids, `attacks` lines are the
# rounds). docs/testing.md, "Companions in a fight", says why each is there and what to do when one fails.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${EXE:-kotor/out/kotor.exe}
out=kotor/out/combat
ck=kotor/out/checkpoints
mkdir -p $out
fail=0

for need in bunk uppercity; do
  if [ ! -d $ck/$need ]; then echo "no checkpoint $ck/$need: run sh kotor/tools/checkpoints/make.sh first"; exit 2; fi
done

# check NAME MEMBER FROM TO: MEMBER's attack rounds in the frames FROM..TO of the log companions_NAME.log
check() {
  name=$1; member=$2; from=$3; to=$4
  log=$out/companions_$name.log
  id=$(grep -a -E "^party [0-9]+: [0-9]+ $member\$" $log | head -1 | sed -E 's/^party [0-9]+: ([0-9]+) .*/\1/')
  if [ -z "$id" ]; then echo "FAIL $name: $member is not in the party (no 'party N: ID $member' line in $log)"; fail=1; return; fi
  n=$(grep -a -E "^\[[0-9]+ [0-9.]+\] $id attacks [0-9]+:" $log | awk -F'[][ ]+' -v from=$from -v to=$to '$2 >= from && $2 <= to' | wc -l)
  if [ "$n" -ge 1 ]; then
    echo "ok   $name: $member made $n attack rounds in frames $from-$to"
  else
    echo "FAIL $name: $member made no attack in frames $from-$to (see $log): the original's companion fights there"
    fail=1
  fi
}

# The Endar Spire from the bunk: the replay's own resume lines up to the bot's start (they hold the reply queue, the
# bot's cheats and its route), then probes; the bot is switched off at 7690 for the bridge fight.
{
  grep -v '^#' $ck/bunk.txt | grep -v '^[[:space:]]*$' | awk '$1 <= 11'
  echo "50 ui party"
  echo "7690 ui bot off"
  echo "7700 use end_door08"
} | sort -s -n -k1,1 > $out/companions_endar.txt
rm -rf $out/saves_companions
$exe --load $ck/bunk --no-render --speed 8 --saves $out/saves_companions --input $out/companions_endar.txt --frames 8500 \
  --log combat > $out/companions_room3.log 2>&1
cp $out/companions_room3.log $out/companions_bridge.log
check room3 Trask 1 3000
check bridge Trask 7600 8500

# Carth in the Upper City.
{
  echo "50 ui party"
  cat kotor/tools/combat/retarget1.txt
} | sort -s -n -k1,1 > $out/companions_upper.txt
rm -rf $out/saves_companions
$exe --load $ck/uppercity --no-render --speed 8 --saves $out/saves_companions --input $out/companions_upper.txt --frames 900 \
  --log combat > $out/companions_carth.log 2>&1
check carth Carth 1 900

if [ $fail -ne 0 ]; then echo "companions: FAILED"; exit 1; fi
echo "companions: ok"
