#!/bin/sh
# The Endar Spire's Jedi duel behind the closed door (docs/design/vfx.md, "World emitters" and the particle
# rules): from the `bunk` checkpoint the replay walks to the door while the duel's lightsaber clashes throw
# v_spkb_imp sparks on the far side. Two runs of the same replay, each with a fixed camera from frame 4000:
#
#   beside  a camera in the duel's room, looking at the duellists; a shot 3 frames after each of the first
#           three clashes from frame 4005 must have at least 100 of the sparks' bright cores: the sparks draw.
#   door    a camera in front of the closed door; shots at the same clashes and after them (4320, 4380) must
#           each have at most 40 spark pixels: the sparks fall to the floor (gravity is world -Z, the
#           particles bounce off the rooms), not fly 30 m down the corridor through the door.
#
# kotor/tools/py/spark_pixels.py counts the pixels of each shot.
#
#   sh kotor/tools/gfx/duel_sparks.sh [EXE]       (from the repository root; EXE defaults to kotor/out/kotor.exe;
#                                                  needs kotor/out/checkpoints/bunk, kotor/tools/checkpoints/make.sh)
#
# PASS: both runs' shots pass (beside: 190 to 490 bright spark pixels each; door: the bug had 130 in one shot,
# fixed 0 to 7). The clashes move whenever the fight's dice do, so a first run without pictures finds them
# (the `vfx v_spkb_imp` lines of --log trace).
py=$(command -v python)    # before the PATH change below: the MSYS2 python has no PIL
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${1:-kotor/out/kotor.exe}
out=kotor/out/gfx/duel_sparks
ck=kotor/out/checkpoints
if [ ! -d $ck/bunk ]; then echo "no checkpoint $ck/bunk: run sh kotor/tools/checkpoints/make.sh first"; exit 2; fi
mkdir -p $out/saves

# run NAME "CAMERA" FRAMES SHOT...: the replay with `cam at CAMERA` from frame 4000, a picture per SHOT
run() {
    name=$1 cam=$2 frames=$3
    shift 3
    awk -v cam="$cam" 'BEGIN{d=0} /^[0-9]/{ if(!d && $1+0>4000){print "4000 cam at " cam; d=1} } {print}' \
        $ck/bunk.txt > $out/$name.txt
    shots=""
    for f in "$@"; do shots="$shots --screenshot-at $f:$out/${name}_$f.png"; done
    $exe --load $ck/bunk --no-render --speed 8 --mute --saves $out/saves --input $out/$name.txt --frames $frames \
        $shots > $out/$name.log 2>&1
}

# The first three clashes from frame 4005, each shot 3 frames later.
awk 'BEGIN{d=0} /^[0-9]/{ if(!d && $1+0>4000){print "4000 cam at 32.5,116.5,2.2 29.8,119.8,1.2"; d=1} } {print}' \
    $ck/bunk.txt > $out/find.txt
$exe --load $ck/bunk --no-render --speed 8 --mute --saves $out/saves --input $out/find.txt --frames 4300 \
    --log trace > $out/find.log 2>&1
clashes=$(grep 'v_spkb_imp' $out/find.log | tr -d '[' | awk '$1+0 >= 4005 && $1+0 <= 4290 { print $1 + 3 }' | sort -n -u | head -3)
if [ $(echo $clashes | wc -w) -lt 3 ]; then echo "fewer than three clashes after frame 4005: $clashes"; exit 2; fi
run beside "32.5,116.5,2.2 29.8,119.8,1.2" 4300 $clashes
run door "29,98,1.6 28.5,112,1.3" 4390 $clashes 4320 4380
ok=1
beside="" door=""
for f in $clashes; do beside="$beside $out/beside_$f.png"; door="$door $out/door_$f.png"; done
"$py" kotor/tools/py/spark_pixels.py --at-least 100 $beside || ok=0
"$py" kotor/tools/py/spark_pixels.py 40 $door $out/door_4320.png $out/door_4380.png || ok=0
if [ $ok = 1 ]; then echo PASS; else echo FAIL; exit 1; fi
