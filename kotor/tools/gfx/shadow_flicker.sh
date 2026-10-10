#!/bin/sh
# The enhanced renderer's shadows hold still (docs/design/enhanced-render.md, "Shadows"): the `bridge` checkpoint's
# replay (the leader runs the Endar Spire's corridors past their shadow-casting lights, through camera cuts and into
# the next area) drawn for 2400 frames with Soft shadow maps and Soft Shadows on, every frame logged with
# --log shadows; kotor/tools/py/shadow_flips.py then counts the frames whose shadows switch between the maps and
# the original's volumes, and the frames where a light's shadow pops in or out (its weight jumps by more than
# 0.25) other than at a cut.
#
#   sh kotor/tools/gfx/shadow_flicker.sh [EXE]    (from the repository root; EXE defaults to kotor/out/kotor.exe;
#                                                  CK=DIR for the checkpoints, default kotor/out/checkpoints)
#
# PASS: 0 mode flips and 0 pops (the bug: 3 flips and 98 pops in the same replay, a light's shadow appearing or
# vanishing in one frame about once a second). About 15 s.
py=$(command -v python)    # before the PATH change below: the MSYS2 python has no PIL
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${1:-kotor/out/kotor.exe}
ck=${CK:-kotor/out/checkpoints}
out=kotor/out/gfx/shadow_flicker
if [ ! -d $ck/bridge ]; then echo "no checkpoint $ck/bridge: run sh kotor/tools/checkpoints/make.sh first"; exit 2; fi
rm -rf $out
mkdir -p $out/saves
{ echo "1 gfx shadowmaps 2"; echo "1 gfx softshadows 1"; tail -n +2 $ck/bridge.txt; } > $out/input.txt
$exe --load $ck/bridge --headless --saves $out/saves --input $out/input.txt --frames 2400 --log shadows > $out/run.log 2>&1
"$py" kotor/tools/py/shadow_flips.py $out/run.log --max-mode 0 --max-pops 0
