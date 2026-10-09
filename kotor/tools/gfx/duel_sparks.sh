#!/bin/sh
# The Endar Spire's Jedi duel behind the closed door (docs/design/vfx.md, "World emitters" and the particle
# rules): from the `bunk` checkpoint the replay walks to the door while the duel's lightsaber clashes throw
# v_spkb_imp sparks on the far side; a camera fixed in front of the closed door takes four shots during the
# clashes. The sparks must fall to the floor by them (gravity is world -Z, the particles bounce off the
# rooms), not fly 30 m down the corridor through the door. kotor/tools/py/spark_pixels.py counts the
# spark-yellow pixels of each shot.
#
#   sh kotor/tools/gfx/duel_sparks.sh [EXE]       (from the repository root; EXE defaults to kotor/out/kotor.exe;
#                                                  needs kotor/out/checkpoints/bunk, kotor/tools/checkpoints/make.sh)
#
# PASS: every shot has at most 40 spark pixels (the bug: 130 in the second shot; fixed: 7 or less). The shots'
# frames count from the checkpoint's load: rebuilt checkpoints may move the clashes (the log's `vfx v_spkb_imp`
# lines with --log trace say when they are).
py=$(command -v python)    # before the PATH change below: the MSYS2 python has no PIL
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${1:-kotor/out/kotor.exe}
out=kotor/out/gfx/duel_sparks
ck=kotor/out/checkpoints
if [ ! -d $ck/bunk ]; then echo "no checkpoint $ck/bunk: run sh kotor/tools/checkpoints/make.sh first"; exit 2; fi
mkdir -p $out/saves
awk 'BEGIN{d=0} /^[0-9]/{ if(!d && $1+0>4200){print "4200 cam at 29,98,1.6 28.5,112,1.3"; d=1} } {print}' $ck/bunk.txt > $out/input.txt
$exe --load $ck/bunk --no-render --speed 8 --mute --saves $out/saves --input $out/input.txt --frames 4420 \
  --screenshot-at 4320:$out/a.png --screenshot-at 4350:$out/b.png --screenshot-at 4380:$out/c.png \
  --screenshot-at 4410:$out/d.png > $out/run.log 2>&1
"$py" kotor/tools/py/spark_pixels.py 40 $out/a.png $out/b.png $out/c.png $out/d.png && echo PASS
