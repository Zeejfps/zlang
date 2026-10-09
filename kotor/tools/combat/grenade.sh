#!/bin/sh
# Does the target block keep its hostile actions off a party member, and does a grenade fly? From `uppercity`
# (kotor/tools/checkpoints/make.sh), with kotor/tools/combat/gren1.txt: Carth targeted (the block's three lists must
# be empty: no attack, no power, no grenade), then a hostile trooper 11 m away targeted and a frag grenade thrown
# through the block's right slot. The throw must land after the projectile's flight (spells.2da Proj 1:
# d / (3 ln d + 2) s, about 1.2 s at 11 m), not at the release 800 ms into the throw.
#
#   sh kotor/tools/combat/grenade.sh            (EXE=kotor/out/kotor.exe; run from the repository root; about 5 seconds)
#
# The logs are kotor/out/combat/gren1.log, grens.log and gren2.log. docs/re/gui.md "What the target block offers", docs/re/render-gui.md
# "Spell projectiles", docs/mechanics/combat.md rows 31-32.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${EXE:-kotor/out/kotor.exe}
out=kotor/out/combat
ck=kotor/out/checkpoints
mkdir -p $out
if [ ! -d $ck/uppercity ]; then echo "no checkpoint $ck/uppercity: run sh kotor/tools/checkpoints/make.sh first"; exit 2; fi
rm -rf $out/saves_gren1
$exe --load $ck/uppercity --no-render --speed 8 --saves $out/saves_gren1 --input kotor/tools/combat/gren1.txt --frames 130 --log combat > $out/gren1.log 2>&1
log=$out/gren1.log
fail=0

# The first fight line is Carth's block, the second the trooper's.
fights=$(grep -a '^fight leader' $log)
party=$(echo "$fights" | sed -n 1p | sed -E 's/.* block (.*)$/\1/')
foe=$(echo "$fights" | sed -n 2p | sed -E 's/.* block (.*)$/\1/')
if [ "$party" != "[] [] []" ]; then
  echo "FAIL a party member's block offers '$party' (want '[] [] []')"; fail=1
fi
case "$foe" in
  *"[*10:"*"6:i_attack]"*"8:iw_fraggren_001"*) ;;
  *) echo "FAIL the hostile trooper's block offers '$foe' (want feats and Attack, then the grenade)"; fail=1 ;;
esac
# The throw: released at tick T, landing N ms later; the trooper takes its damage then (30 ticks a second).
throw=$(grep -a -E '^\[[0-9]+ [0-9.]+\] [0-9]+ throws 87 at .*lands in [0-9]+ ms' $log | head -1)
if [ -z "$throw" ]; then
  echo "FAIL no grenade was thrown (see $log)"; fail=1
else
  at=$(echo "$throw" | sed -E 's/^\[([0-9]+) .*/\1/')
  ms=$(echo "$throw" | sed -E 's/.*lands in ([0-9]+) ms.*/\1/')
  foe_id=$(grep -a -E '^spawn g_sithtroop02 [0-9]+ ' $log | head -1 | awk '{print $3}')
  hit=$(grep -a -E "^\[[0-9]+ [0-9.]+\] $foe_id takes [0-9]+ damage from 2147483647" $log | head -1 | sed -E 's/^\[([0-9]+) .*/\1/')
  want=$((at + ms * 30 / 1000))
  if [ "$ms" -lt 1000 ] || [ "$ms" -gt 1400 ]; then echo "FAIL the flight took $ms ms (want about 1200 at 11 m)"; fail=1; fi
  if [ -z "$hit" ]; then
    echo "FAIL the trooper took no grenade damage (see $log)"; fail=1
  elif [ $((hit - want)) -lt -1 ] || [ $((hit - want)) -gt 2 ]; then
    echo "FAIL the grenade hit at tick $hit, want about $want (released at $at, $ms ms of flight)"; fail=1
  fi
fi
if [ $fail = 0 ]; then echo "ok   grenade: nothing offered on Carth; the throw left at tick $at and landed $ms ms later (hit at $hit)"; fi

# Saved in flight (gren_save.txt: the same throw, `save` 10 ticks after the release, `load` at once): the impact is
# in the save's event queue (SPELL_IMPACT, EventData 0x6666, as the original's SaveEvent 0x004afea0), so the trooper
# still takes the grenade, the flight time left after the load.
rm -rf $out/saves_grens
$exe --load $ck/uppercity --no-render --speed 8 --saves $out/saves_grens --input kotor/tools/combat/gren_save.txt --frames 200 --log combat,module > $out/grens.log 2>&1
slog=$out/grens.log
saved=$(grep -a -E '^\[[0-9]+ [0-9.]+\] saved ' $slog | head -1 | sed -E 's/^\[[0-9]+ ([0-9.]+)\].*/\1/')
loaded=$(grep -a -E '^\[[0-9]+ [0-9.]+\] loaded .*saves_grens' $slog | head -1 | sed -E 's/^\[([0-9]+) .*/\1/')
sthrow=$(grep -a -E '^\[[0-9]+ [0-9.]+\] [0-9]+ throws 87 at .*lands in [0-9]+ ms' $slog | head -1)
shit=$(grep -a -E '^\[[0-9]+ [0-9.]+\] [0-9]+ takes [0-9]+ damage from 2147483647' $slog | head -1 | sed -E 's/^\[([0-9]+) .*/\1/')
if [ -z "$saved" ] || [ -z "$loaded" ] || [ -z "$sthrow" ]; then
  echo "FAIL the in-flight save run did not throw, save and load (see $slog)"; fail=1
elif [ -z "$shit" ]; then
  echo "FAIL a grenade saved in flight never landed after the load (see $slog)"; fail=1
elif [ "$shit" -le "$loaded" ]; then
  echo "FAIL the grenade saved in flight hit at tick $shit, before the load at $loaded"; fail=1
else
  echo "ok   grenade saved in flight: loaded at tick $loaded, landed at $shit"
fi

# An AI throw (gren2.txt): Carth as a grenadier (NPC_AISTYLE 4, k_ai_master's talents) with frag grenades in the bag,
# two troopers 9-10 m off engaging the party. He must throw one on his own, it must fly the grenade path (four legs:
# the scene rays found the ground under the three bounce points) and land after its flight, hurting the troopers.
rm -rf $out/saves_gren2
$exe --load $ck/uppercity --no-render --speed 8 --saves $out/saves_gren2 --input kotor/tools/combat/gren2.txt --frames 300 --log combat > $out/gren2.log 2>&1
alog=$out/gren2.log
# The thrower is the party member who is not the player's creature (2147483647).
athrow=$(grep -a -E '^\[[0-9]+ [0-9.]+\] [0-9]+ throws 87 at .*lands in [0-9]+ ms' $alog | grep -a -v '\] 2147483647 throws' | head -1)
carth=$(echo "$athrow" | awk '{print $3}')
apath=$(grep -a -E '^\[[0-9]+ [0-9.]+\] grenade path: ' $alog | head -1 | sed -E 's/.*grenade path: ([0-9]+) legs.*/\1/')
if [ -z "$carth" ] || [ -z "$athrow" ]; then
  echo "FAIL Carth threw no grenade on his own (see $alog)"; fail=1
else
  aat=$(echo "$athrow" | sed -E 's/^\[([0-9]+) .*/\1/')
  ams=$(echo "$athrow" | sed -E 's/.*lands in ([0-9]+) ms.*/\1/')
  ahit=$(grep -a -E "^\[[0-9]+ [0-9.]+\] [0-9]+ takes [0-9]+ damage from $carth:" $alog | head -1 | sed -E 's/^\[([0-9]+) .*/\1/')
  awant=$((aat + ams * 30 / 1000))
  # The bounce points lie on the floor the troopers stand on, not on something overhead (a sky dome seen from above).
  agap=$(grep -a -E '^\[[0-9]+ [0-9.]+\] grenade path: ' $alog | head -1 | sed -E 's/.*ground ([^ ]+) ([^ ]+) ([^,]+), target z (.*)$/\1 \2 \3 \4/' | awk '{m = 0; for (i = 1; i <= 3; i++) { d = $i - $4; if (d < 0) d = -d; if (d > m) m = d } print (m < 2.0) ? "ok" : m}')
  if [ "$apath" != 4 ]; then
    echo "FAIL Carth's grenade flew '$apath' legs (want 4: the ground under the bounce points)"; fail=1
  elif [ "$agap" != ok ]; then
    echo "FAIL a bounce point of Carth's grenade is $agap m off the target's floor"; fail=1
  elif [ -z "$ahit" ]; then
    echo "FAIL Carth's grenade hurt nobody (see $alog)"; fail=1
  elif [ $((ahit - awant)) -lt -1 ] || [ $((ahit - awant)) -gt 2 ]; then
    echo "FAIL Carth's grenade hit at tick $ahit, want about $awant (thrown at $aat, $ams ms of flight)"; fail=1
  else
    echo "ok   AI grenade: Carth threw at tick $aat, $apath legs, landed at $ahit"
  fi
fi
exit $fail
