#!/bin/sh
# The Endar Spire's Jedi duel behind the closed door (docs/design/vfx.md, "World emitters" and the particle
# rules): from the `bunk` checkpoint the replay walks to the door while the duel's lightsaber clashes throw
# v_spkb_imp sparks on the far side. Two runs of the same replay, each with a fixed camera from frame 4000:
#
#   beside  a camera in the duel's room, looking at the duellists; three shots at clashes (4036, 4183, 4233)
#           must each have at least 100 of the sparks' bright cores: the sparks still draw.
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
# fixed 0 to 7). The shots' frames count from the checkpoint's load: rebuilt checkpoints may move the clashes
# (the log's `vfx v_spkb_imp` lines with --log trace say when they are; the last is near frame 4227).
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

run beside "32.5,116.5,2.2 29.8,119.8,1.2" 4240 4036 4183 4233
run door "29,98,1.6 28.5,112,1.3" 4390 4036 4183 4233 4320 4380
ok=1
"$py" kotor/tools/py/spark_pixels.py --at-least 100 $out/beside_4036.png $out/beside_4183.png $out/beside_4233.png || ok=0
"$py" kotor/tools/py/spark_pixels.py 40 $out/door_4036.png $out/door_4183.png $out/door_4233.png $out/door_4320.png \
    $out/door_4380.png || ok=0
if [ $ok = 1 ]; then echo PASS; else echo FAIL; exit 1; fi
