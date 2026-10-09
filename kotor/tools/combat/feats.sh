#!/bin/sh
# The target block's combat feats in a fight, each against the rules (docs/re/combat.md 4.5, 3.1 step 4):
#
#   EXE=kotor/out/kotor.exe sh kotor/tools/combat/feats.sh [CASE...]
#
# From the `uppercity` checkpoint each case gives the leader a weapon and one feat, puts a Sith trooper
# ahead, picks the feat in the block's first slot (`ui slotpick`, the arrows' choice) and clicks BTN_TARGET0
# four times: once to start, three more queued in combat mode. With `--log combat` every round of the leader
# that carries the feat must show: the number of attacks (1, +1 for the Flurry / Rapid Shot lines, +1 off hand
# with two weapons or a double weapon), the feat's own animation for the stance (f<d>a1..3 melee, b<d>a2..4
# ranged; the plain shot b<d>a1), the to-hit (`special`), the damage bonus on a hit (`bonus`), the lowest
# threatening d20 (`threat`: 21 - CritThreat x (1 + rank) for Critical Strike / Sniper Shot), the defense
# penalty put on the leader at once (`feat F on L: defense -P`) and the stun save on a first-attack hit of
# Critical Strike / Sniper Shot (`stun 1`); the summary line says "<feat> used". Logs in kotor/out/combat/feats.
# SHOTS="F1 F2 ..." also takes a picture at those frames (kotor/out/combat/feats/NAME_F.png): the leader's
# first round starts at frame 104 in melee, 44-47 at range. Prints one line per case and FAIL lines; exit 1 on
# any failure. Bare hands (right "-"): the feat still adds its attack but the attacks are plain (feat 0 in the
# lines, no penalty, no "used"): the original writes the AttackType only with a right-hand item (combat.md 4.5).
# A stun baton in the left hand beside a sword is stance digit 0, whose attack row is 0 (3.1 step 4).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
EXE=${EXE:-kotor/out/kotor.exe}
out=kotor/out/combat/feats
mkdir -p $out

# name feat right left digit dist attacks row special bonus penalty rank threat
cases='
crit1     8  g_w_vbroswrd01  -               2 6  1 113  0  0 5 1 17
crit2     19 g_w_vbroswrd01  -               2 6  1 113  0  0 5 2 15
crit3     81 g_w_vbroswrd01  -               2 6  1 113  0  0 5 3 13
flurry1   11 g_w_vbroswrd01  -               2 6  2 114 -4  0 4 0 19
flurry2   91 g_w_vbroswrd01  -               2 6  2 114 -2  0 2 0 19
flurry3   53 g_w_vbroswrd01  -               2 6  2 114 -1  0 1 0 19
power1    28 g_w_vbroswrd01  -               2 6  1 115 -3  5 0 0 19
power2    17 g_w_vbroswrd01  -               2 6  1 115 -3  8 0 0 19
power3    83 g_w_vbroswrd01  -               2 6  1 115 -3 10 0 0 19
sniper1   31 g_w_blstrpstl001 -              5 12 1 219  0  0 5 1 19
sniper2   20 g_w_blstrpstl001 -              5 12 1 219  0  0 5 2 18
sniper3   77 g_w_blstrpstl001 -              5 12 1 219  0  0 5 3 17
rapid1    30 g_w_blstrpstl001 -              5 12 2 218 -4  0 4 0 20
rapid2    92 g_w_blstrpstl001 -              5 12 2 218 -2  0 2 0 20
rapid3    26 g_w_blstrpstl001 -              5 12 2 218 -1  0 1 0 20
blast1    29 g_w_blstrpstl001 -              5 12 1 362 -3  5 0 0 20
blast2    18 g_w_blstrpstl001 -              5 12 1 362 -3  8 0 0 20
blast3    82 g_w_blstrpstl001 -              5 12 1 362 -3 10 0 0 20
plainshot 0  g_w_blstrpstl001 -              5 12 1 217  0  0 0 0 20
plainmelee 0 g_w_vbroswrd01  -               2 6  1 -    0  0 0 0 19
dsaber    11 g_w_dblswrd001  -               3 6  3 155 -4  0 4 0 20
baton     28 g_w_stunbaton01 -               1 6  1 87  -3  5 0 0 20
twinsaber 8  g_w_vbroswrd01  g_w_vbroshort01 4 6  2 195  0  0 5 1 17
rifle     29 g_w_blstrrfl001 -               7 12 1 364 -3  5 0 0 19
twinpstl  31 g_w_blstrpstl001 g_w_blstrpstl001 6 12 2 233 0 0 5 1 19
repeater  30 g_w_rptnblstr01 -               9 12 2 353 -4  0 4 0 20
unflurry  11 -               -               8 6  2 -    0  0 0 0 20
unpower   28 -               -               8 6  1 -    0  0 0 0 20
batonleft 0  g_w_vbroswrd01  g_w_stunbaton01 0 6  2 0    0  0 0 0 -
'
fails=0
run_case() {
    name=$1; feat=$2; right=$3; left=$4; dist=$6
    in=$out/$name.txt
    {
        echo "20 ui heal"
        echo "21 ui sethp pc 400"
        # Strong enough to hit AC 19 most of the time, so the hits' numbers are checked too.
        echo "21 ui stat str 30"
        echo "21 ui stat dex 30"
        if [ "$right" = "-" ]; then echo "21 ui unequip 4"; echo "21 ui unequip 5"; else echo "21 ui giveitem $right 1 equip"; fi
        [ "$left" != "-" ] && echo "21 ui giveitem $left 1 left"
        [ "$feat" != 0 ] && echo "22 ui grantfeat $feat"
        echo "30 ui foe g_sithtroop01 $dist -3"
        echo "31 cam toward g_sithtroop01"
        echo "32 ui sethp g_sithtroop01 400"
        echo "40 ui target g_sithtroop01"
        if [ "$feat" = 0 ]; then
            for f in 44 46 48 50; do echo "$f ui key r"; done
        else
            echo "44 ui slotpick 0 $feat"
            for f in 46 48 50 52; do echo "$f ui clicktag BTN_TARGET0"; done
        fi
        echo "56 ui fight"
    } > $in
    shots=""
    for s in $SHOTS; do shots="$shots --screenshot-at $s:$out/${name}_$s.png"; done
    rm -rf $out/saves_$name
    $EXE --load kotor/out/checkpoints/uppercity --no-render --speed 8 --saves $out/saves_$name \
        --input $in --frames ${FRAMES:-520} --log combat $shots > $out/$name.log 2>&1
}

# Up to four at a time.
n=0
echo "$cases" | { while read name feat right left digit dist attacks row special bonus penalty rank threat; do
    [ -z "$name" ] && continue
    if [ $# -gt 0 ]; then case " $* " in *" $name "*) ;; *) continue ;; esac; fi
    run_case $name $feat $right $left $digit $dist &
    n=$((n + 1))
    [ $((n % 4)) = 0 ] && wait
done; wait; }
wait

echo "$cases" | {
while read name feat right left digit dist attacks row special bonus penalty rank threat; do
    [ -z "$name" ] && continue
    if [ $# -gt 0 ]; then case " $* " in *" $name "*) ;; *) continue ;; esac; fi
    log=$out/$name.log
    # The feat the attack lines carry: none with bare hands.
    E=$feat; [ "$right" = "-" ] && E=0
    res=$(awk -v F=$E -v N=$attacks -v R=$row -v S=$special -v B=$bonus -v P=$penalty -v T=$threat -v STUN=$rank '
        /^fault/ { faults++ }
        / used\. / && /log \(red\): Player/ { used++ }
        /  feat [0-9]+ on 2147483647: defense -/ { pen[$0 ~ ("feat " F " on") ? "f" : "x"]++; pv = $0; sub(/.*defense -/, "", pv); sub(/ .*/, "", pv); if (pv + 0 != P) bad = bad " penalty" pv }
        /^\[[0-9]+ [0-9.]+\]   attack [0-9]+: d20/ {
            na++; line[na] = $0; next
        }
        / attacks [0-9]+: [0-9]+ attacks, animation / {
            split($0, w, " ")
            who = w[3]
            if (who == "2147483647") {
                f = -1
                for (i = 1; i <= na; i++) { if (match(line[i], /feat -?[0-9]+/)) { f = substr(line[i], RSTART + 5, RLENGTH - 5) + 0 } }
                if (f == F && (F != 0 || rounds < 4)) {
                    rounds++
                    cnt = w[6] + 0; anim = w[9] + 0
                    if (cnt != N) bad = bad " attacks" cnt
                    if (R != "-" && anim != R) bad = bad " animation" anim
                    for (i = 1; i <= na; i++) {
                        split(line[i], a, " ")
                        # [fr t] attack k: d20 D total X vs Y result Z damage M at H ms feat F threat T special S bonus B stun s r
                        idx = a[4] + 0; result = a[12] + 0
                        thr = a[21] + 0; sp = a[23] + 0; bo = a[25] + 0; st = a[27]
                        if (sp != S) bad = bad " special" sp
                        hit = (result >= 1 && result <= 3)
                        if ((result == 1 || result == 2) && T != "-" && thr != T) bad = bad " threat" thr
                        hit = (result >= 1 && result <= 3)
                        if (hit && bo != B) bad = bad " bonus" bo
                        if (STUN > 0 && idx == 1 && hit && st != "true") bad = bad " nostun"
                        if (STUN == 0 && st != "false") bad = bad " stun"
                        if (hit) hits++
                    }
                }
            }
            na = 0
        }
        END {
            if (rounds < 4) bad = bad " rounds" rounds
            if (F != 0 && used < 1) bad = bad " noused"
            if (P > 0 && pen["f"] < rounds) bad = bad " penalties" pen["f"] "/" rounds
            if (P == 0 && pen["f"] > 0) bad = bad " penalty_on_" pen["f"]
            printf "rounds %d hits %d used %d faults %d%s\n", rounds, hits, used, faults, (bad == "" ? "" : " BAD" bad)
        }' $log)
    case "$res" in
        *BAD*|*"faults "[1-9]*) echo "FAIL $name (feat $feat, $right): $res"; fails=$((fails + 1)) ;;
        *) echo "ok   $name (feat $feat, digit $digit, row $row): $res" ;;
    esac
done
echo "feats: $fails failed"
[ $fails = 0 ]
}
