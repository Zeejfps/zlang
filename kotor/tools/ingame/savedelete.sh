#!/bin/sh
# Delete in the save lists (docs/re/gui.md "Save and load", Delete): scripts/savedelete1.txt makes two
# manual saves, then scripts/savedelete2.txt hilights the newer one in Save Game, presses Delete and answers
# Yes to 1592. FAIL (exit 1) unless the newer folder is gone, the older
# one and the quick save are untouched (the same files, byte for byte), the list was filled again (New Slot
# and the one save, Delete still enabled for it), the install's autosave has Delete disabled in Load Game, and
# the install's Saves/ is unchanged. Pictures in kotor/out/savedelete: before.png (Save Game, the newer save
# hilighted), confirm.png (1592), after.png (the list after: New Slot and "Game 1"), install.png (Load Game,
# the install's autosave hilighted, Delete greyed).
#
#   EXE=kotor/out/kotor.exe sh kotor/tools/ingame/savedelete.sh   (from the repository root; CHECKPOINTS=DIR in a worktree)
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${EXE:-kotor/out/kotor.exe}
ck=${CHECKPOINTS:-kotor/out/checkpoints}
install=${INSTALL_SAVES:-/f/Steam/steamapps/common/swkotor/saves}
out=kotor/out/savedelete
saves=$out/saves
in=kotor/tools/ingame/scripts/savedelete
if [ ! -d $ck/cantina ]; then echo "no checkpoint $ck/cantina: run sh kotor/tools/checkpoints/make.sh first"; exit 2; fi
rm -rf $out
mkdir -p $saves
fail=0
sums() { (cd "$1" && find . -type f | sort | xargs -d '\n' md5sum 2>/dev/null) | md5sum | cut -c1-32; }
installed=$(ls -lR "$install" 2>/dev/null | md5sum | cut -c1-32)
$exe --load $ck/cantina --headless --saves $saves --frames 66 --input ${in}1.txt > $out/run1.log 2>&1
old="$saves/000002 - Game1"
new="$saves/000003 - Game2"
quick="$saves/000000 - QUICKSAVE"
if [ ! -f "$old/savenfo.res" ] || [ ! -f "$new/savenfo.res" ]; then echo "FAIL the first run did not make both saves ($out/run1.log)"; exit 1; fi
old_sum=$(sums "$old")
quick_sum=$(sums "$quick")
$exe --load $ck/cantina --headless --saves $saves --frames 112 --input ${in}2.txt --log objects \
  --screenshot-at 81:$out/before.png --screenshot-at 87:$out/confirm.png --screenshot-at 95:$out/after.png \
  --screenshot-at 110:$out/install.png > $out/run2.log 2>&1
[ -e "$new" ] && { echo "FAIL $new is still there"; fail=1; }
folders=$(ls $saves | grep '^[0-9][0-9][0-9][0-9][0-9][0-9] - ' | tr '\n' '|')
[ "$folders" = "000000 - QUICKSAVE|000002 - Game1|" ] || { echo "FAIL save folders after the delete: $folders"; fail=1; }
[ "$(sums "$old")" = "$old_sum" ] || { echo "FAIL $old changed"; fail=1; }
[ "$(sums "$quick")" = "$quick_sum" ] || { echo "FAIL $quick changed"; fail=1; }
ctl=$(grep -a '^ctl: BTN_DELETE\|^ctl: LB_GAMES' $out/run2.log | sed 's/ in .* visible / visible /; s/ text .*//')
first=$(echo "$ctl" | sed -n 1p)
rows=$(echo "$ctl" | grep LB_GAMES | sed -n 1p)
after=$(echo "$ctl" | grep BTN_DELETE | sed -n 2p)
inst=$(echo "$ctl" | grep BTN_DELETE | sed -n 3p)
case "$first" in *"visible true enabled true"*) ;; *) echo "FAIL Delete for our save: $first"; fail=1;; esac
case "$rows" in *"rows 2"*) ;; *) echo "FAIL the Save Game list after the delete: $rows (want New Slot and one save)"; fail=1;; esac
case "$after" in *"enabled true"*) ;; *) echo "FAIL Delete after the delete: $after"; fail=1;; esac
if ! ls "$install" 2>/dev/null | grep -q '^000001 - '; then
  echo "skip the install's autosave check: $install has none"
else
  case "$inst" in *"visible true enabled false"*) ;; *) echo "FAIL Delete for the install's autosave: $inst"; fail=1;; esac
fi
[ "$(ls -lR "$install" 2>/dev/null | md5sum | cut -c1-32)" = "$installed" ] || { echo "FAIL $install changed"; fail=1; }
faults=$(cat $out/run1.log $out/run2.log | grep -a -c '^fault')
[ "$faults" = 0 ] || { echo "FAIL $faults faults"; fail=1; }
[ $fail = 0 ] && echo "ok   savedelete: $(basename "$new") deleted, $(basename "$old") and the quick save untouched, the install's autosave not deletable; pictures in $out"
exit $fail
