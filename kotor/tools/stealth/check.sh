#!/bin/sh
# Runs the stealth scenarios through the mouse and keys and checks what they log
# (docs/mechanics/stealth.md). Run it from the repository root after building EXE (default
# kotor/out/kotor_stl.exe); the uppercity scenario needs the checkpoints (docs/testing.md).
#
#   sh kotor/tools/stealth/check.sh
#
# A pattern must appear in the scenario's log; one starting with ! must not appear in its full log.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
fails=0
dir=kotor/tools/stealth/scripts

# expect NAME START SCRIPT FRAMES "pattern"...
expect() {
  name=$1; start=$2; script=$3; frames=$4; shift 4
  res=$(sh kotor/tools/stealth/run.sh "$name" "$start" "$dir/$script" "$frames")
  case "$res" in *" 0 faults"*) ;; *) echo "FAIL $name: $res"; fails=$((fails + 1)) ;; esac
  for pat in "$@"; do
    case "$pat" in
      !*) if grep -a -q -- "${pat#!}" "kotor/out/stealth/$name.raw"; then
            echo "FAIL $name: a line matching '${pat#!}'"; fails=$((fails + 1)); fi ;;
      *) if ! grep -a -q -- "$pat" "kotor/out/stealth/$name.log"; then
           echo "FAIL $name: no line matching '$pat'"; fails=$((fails + 1)); fi ;;
    esac
  done
  echo "ran $name"
}

expect walk_past module:end_m01ab walk_past.txt 600 "enters stealth mode" "on true toggle true solo false party 1 combat false xp 300/300 enabled true at 76" "!attacks 2147483647"
expect walk_control module:end_m01ab walk_control.txt 600 "combat true xp 0/300" "!enters stealth mode"
expect attack_out module:end_m01ab attack_out.txt 900 "leaves stealth mode" "noticed the party: stealth XP 300 -> 0"
expect key_unequip module:end_m01ab key_unequip.txt 200 "^pos 55\.8" "leaves stealth mode" "on false toggle false solo false party 1"
expect combat_refused module:end_m01ab combat_refused.txt 310 "log: You cannot enter stealth mode while in combat." "!enters stealth mode"
expect solo_box uppercity solo_box.txt 245 "on true toggle true solo true party 2" "^stealth: [0-9]* on false toggle false solo true party 2 combat false xp 0/0 enabled false at 9" "on false toggle true solo false party 2"
expect rest module:end_m01ab rest.txt 90 "^rest: [0-9]* true" "^stealth: [0-9]* on false toggle true"
expect rest_refused uppercity rest_refused.txt 90 "^rest: [0-9]* false"
rm -rf kotor/out/stealth/saves_save_hiding       # so the save is the folder's first, 000002 - Game1
expect save_hiding module:end_m01ab save_hiding.txt 90 "on true toggle true solo false party 1"
expect load_hiding "save:kotor/out/stealth/saves_save_hiding/000002 - Game1" load_hiding.txt 10 "on true toggle true solo false party 1 combat false xp 300/300"

if [ "$fails" -eq 0 ]; then echo "all stealth checks passed"; else echo "$fails stealth checks failed"; exit 1; fi
