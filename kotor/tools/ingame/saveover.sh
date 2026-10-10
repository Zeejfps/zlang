#!/bin/sh
# Saving over a save from the Save Game list (docs/re/gui.md "Save and load", docs/re/party-items-saves.md 1.1):
# saveover1.txt quick-saves the cantina checkpoint, then saves it to "New Slot" with the default name; a stray
# file is put in the new folder; saveover2.txt loads that save, plays on, picks it in the list, answers Yes to
# 1591 and renames it. FAIL (exit 1) unless the folders are still the quick save and the one manual save, its
# SAVEGAMENAME and TIMEPLAYED changed (the time grown by the second run's frames before the save, at the fixed
# headless step), and neither the stray file nor a staged one is left. Pictures in kotor/out/saveover:
# list1.png (the Save Game list before), confirm.png (1591), name.png (the name box with the save's name),
# list2.png (the list after: "Game 1 - 0h 31m" and the new name), load.png (Load Game: "Quick Save - 0H 31M",
# then ours and the install's saves by number, each with its play time).
#
#   EXE=kotor/out/kotor.exe sh kotor/tools/ingame/saveover.sh      (from the repository root; about 20 s)
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${EXE:-kotor/out/kotor.exe}
ck=${CHECKPOINTS:-kotor/out/checkpoints}
out=kotor/out/saveover
saves=$out/saves
if [ ! -d $ck/cantina ]; then echo "no checkpoint $ck/cantina: run sh kotor/tools/checkpoints/make.sh first"; exit 2; fi
rm -rf $out
mkdir -p $saves
fail=0
nfo() { python kotor/tools/py/gffpy.py "$1/savenfo.res" 2>/dev/null | grep -a "^$2:" | sed "s/^$2: [A-Za-z]* = //; s/'//g"; }
$exe --load $ck/cantina --headless --saves $saves --frames 40 --input kotor/tools/ingame/scripts/saveover1.txt > $out/run1.log 2>&1
folder="$saves/000002 - Game1"
if [ ! -f "$folder/savenfo.res" ]; then echo "FAIL the first run made no $folder ($out/run1.log)"; exit 1; fi
name1=$(nfo "$folder" SAVEGAMENAME)
time1=$(nfo "$folder" TIMEPLAYED)
echo stray > "$folder/stray.txt"
$exe --load "$folder" --headless --saves $saves --frames 162 --input kotor/tools/ingame/scripts/saveover2.txt --log objects \
  --screenshot-at 108:$out/list1.png --screenshot-at 118:$out/confirm.png --screenshot-at 121:$out/name.png --screenshot-at 149:$out/list2.png \
  --screenshot-at 160:$out/load.png > $out/run2.log 2>&1
name2=$(nfo "$folder" SAVEGAMENAME)
time2=$(nfo "$folder" TIMEPLAYED)
folders=$(ls $saves | grep '^[0-9][0-9][0-9][0-9][0-9][0-9] - ' | tr '\n' '|')
[ "$folders" = "000000 - QUICKSAVE|000002 - Game1|" ] || { echo "FAIL save folders after saving over the manual one: $folders"; fail=1; }
[ "$name2" = "Second save" ] || { echo "FAIL SAVEGAMENAME '$name2' after the save over '$name1', want 'Second save'"; fail=1; }
# The save is made at frame 130 of the second run, 1/30 s a frame: about 4 s more than the first save.
grown=$(( ${time2:-0} - ${time1:-0} ))
if [ $grown -lt 3 ] || [ $grown -gt 6 ]; then echo "FAIL TIMEPLAYED $time1 -> $time2: want about 4 s more"; fail=1; fi
left=$(ls "$folder" | grep -v -x -e SAVEGAME.sav -e GLOBALVARS.res -e PARTYTABLE.res -e savenfo.res -e Screen.tga | xargs)
[ -z "$left" ] || { echo "FAIL left in the save folder: $left"; fail=1; }
grep -aq "saved $folder" $out/run2.log || { echo "FAIL the second run did not save into $folder ($out/run2.log)"; fail=1; }
faults=$(cat $out/run1.log $out/run2.log | grep -a -c '^fault')
[ "$faults" = 0 ] || { echo "FAIL $faults faults"; fail=1; }
[ $fail = 0 ] && echo "ok   saveover: one folder, '$name1' ($time1 s) -> '$name2' ($time2 s), nothing else left; pictures in $out"
exit $fail
