#!/bin/sh
# The key bindings and the remapping screen (docs/mechanics/controls.md, docs/re/gui.md "Key mapping"), from the
# cantina checkpoint with an options file of its own (--settings, so the hidden run reads its [Keymapping]):
# keymap_remap.txt moves Move Forward to I on the screen and accepts (the file must then say Action280A=59 and
# Action210=0, and I must walk while W does not); keymap_reload.txt starts from that file (I walks, W does not),
# then Default and Accept put the defaults back (Action280A=73, Action210=59) and W walks again. Pictures of the
# screen (open, waiting for a key, the changed row, the Game page) in kotor/out/keymap/. FAIL (exit 1) on any step.
#
#   EXE=kotor/out/kotor.exe sh kotor/tools/ingame/keymap.sh      (from the repository root; about 15 s)
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${EXE:-kotor/out/kotor.exe}
ck=kotor/out/checkpoints
out=kotor/out/keymap
mkdir -p $out
if [ ! -d $ck/cantina ]; then echo "no checkpoint $ck/cantina: run sh kotor/tools/checkpoints/make.sh first"; exit 2; fi
rm -f $out/keys.ini
$exe --load $ck/cantina --headless --frames 280 --settings $out/keys.ini --input kotor/tools/ingame/scripts/keymap_remap.txt --log objects \
  --screenshot-at 45:$out/open.png --screenshot-at 60:$out/waiting.png --screenshot-at 85:$out/changed.png --screenshot-at 100:$out/game.png > $out/remap.log 2>&1
fail=0
# The x of each `ui pos` line, in order.
xs() { grep -a '^pos ' $1 | awk '{ print $2 }' | xargs; }
moved() { awk -v a=$1 -v b=$2 'BEGIN { d = b - a; if (d < 0) d = -d; exit !(d > 1.0) }'; }
set -- $(xs $out/remap.log)
if [ $# -lt 4 ] || moved $1 $2 || ! moved $2 $3 || moved $3 $4; then echo "FAIL remap: x [$*]: want still on the screen, moving on I, still on W ($out/remap.log)"; fail=1; fi
grep -q '^Action280A=59' $out/keys.ini && grep -q '^Action210=0' $out/keys.ini || { echo "FAIL remap: $out/keys.ini lacks Action280A=59 / Action210=0"; fail=1; }
cp $out/keys.ini $out/keys2.ini
$exe --load $ck/cantina --no-render --frames 230 --settings $out/keys2.ini --input kotor/tools/ingame/scripts/keymap_reload.txt --log objects > $out/reload.log 2>&1
set -- $(xs $out/reload.log)
if [ $# -lt 4 ] || ! moved $1 $2 || moved $2 $3 || ! moved $3 $4; then echo "FAIL reload: x [$*]: want moving on I, still on W, moving on W after Default ($out/reload.log)"; fail=1; fi
grep -q '^Action280A=73' $out/keys2.ini && grep -q '^Action210=59' $out/keys2.ini || { echo "FAIL reload: $out/keys2.ini lacks Action280A=73 / Action210=59 after Default"; fail=1; }
faults=$(cat $out/remap.log $out/reload.log | grep -a -c '^fault')
if [ "$faults" != 0 ]; then echo "FAIL $faults faults"; fail=1; fi
[ $fail = 0 ] && echo "ok   keymap: I took Move Forward from W (Inventory lost I), kept in the file and read back; Default put them back; pictures in $out"
exit $fail
