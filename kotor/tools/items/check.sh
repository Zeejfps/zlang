#!/bin/sh
# Runs the item and skill scenarios through the mouse and keys and checks what they log
# (docs/mechanics/items-skills.md). Run it from the repository root after building EXE (default
# kotor/out/kotor_itm.exe) and making the checkpoints with it (`EXE=... sh kotor/tools/checkpoints/make.sh`).
#
#   sh kotor/tools/items/check.sh
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
fails=0
dir=kotor/tools/items/scripts

# expect NAME START SCRIPT FRAMES "pattern that must appear in the log"...
expect() {
  name=$1; start=$2; script=$3; frames=$4; shift 4
  res=$(LOG=${LOG:-actions} sh kotor/tools/items/run.sh "$name" "$start" "$dir/$script" "$frames")
  case "$res" in *" 0 faults"*) ;; *) echo "FAIL $name: $res"; fails=$((fails + 1)) ;; esac
  for pat in "$@"; do
    if ! grep -a -q -- "$pat" "kotor/out/items/$name.log"; then
      echo "FAIL $name: no line matching '$pat'"
      fails=$((fails + 1))
    fi
  done
  echo "ran $name"
}

expect inv_click    bunk inv_click.txt        220 "leader hp 18 of 22" "Medpac x1"
expect inv_button   bunk inv_button.txt        50 "BTN_USEITEM.* colour 0.0 0.33 0.49" "BTN_USEITEM.* colour 0.0 0.66 0.98"
rm -rf kotor/out/items/saves_new_saved
expect new_saved    bunk new_saved.txt         120 "ctl: LB_ITEMS in inventory .* rows 1 "
expect equip_prev   bunk equip_preview.txt    160 "worn 1: 202 Clothing" "worn 1: 288 Combat Suit" "worn 1: 289 Heavy Combat Suit"
expect grenade      uppercity grenade.txt     300 "hp -11" "Frag Grenade x3"
expect security     bunk security2.txt        260 "success Security: 25 (roll 20 + Security 5) vs. DC 12"
expect security_sp  bunk security_spike.txt   260 "success Security: 32 (roll 20 + Security 12) vs. DC 28" "Security Spike Tunneler x1"
expect consumables  bunk consumables2.txt     620 "^fx [0-9]* : 7 effects" "leader hp 22 of 22"
expect props        bunk props_effects.txt     60 "^fx [0-9]* : 3 effects" "^fx [0-9]* : 0 effects"
expect medpac_tut   bunk medpac_tutorial.txt  220 "leader hp 18 of 22"
expect one_item     bunk one_item_round3.txt  320 "ctl: LB_MESSAGE in confirm "
expect container    bunk container_give.txt   120 "LB_ITEMS in container.* rows 3 " "tag end_locker01 items 1 " "Medpac x2"
expect slots        bunk slots_lists.txt      130 "LBL_ACTIONDESC.* text 'Full Health'" "LBL_ACTIONDESC.* size 175 32 .* text 'Adrenal Strength (self) (3)'" "LBL_ACTIONDESC.* size 175 16 .* text 'Medpac (self) (2)'"
expect equip_flow   bunk equip_flow.txt       215 "LB_ITEMS in equip.* enabled false rows" "LB_ITEMS in equip.* enabled true rows" "worn 4: 289 Long Sword"
expect equip_dual   bunk equip_dual.txt       125 "worn 5: 289 Long Sword" "worn 4: 280 Blaster Rifle"
expect equip_damage bunk equip_damage.txt     200 "LBL_ATKL.* text '5-16'" "LBL_ATKL.* text '1-11'" "LBL_TOHITR.* text '0' " "LBL_TOHITR.* text '+3' colour 0.28"
expect equip_hide   bunk equip_hide.txt        80 "ctl: LB_ITEMS has no row like 'Jedi'" "ctl: LB_ITEMS in equip .* rows 3 "
expect bench_empty  module:ebo_m12aa bench_empty.txt   200 "ctl: LBL_RANGED .* visible false" "ctl: BTN_RANGED in upgradesel .* enabled true" "ctl: no shown control BTN_RANGED"
expect bench_ranged module:ebo_m12aa bench_ranged.txt  380 "assembled, upgrades 589824 (were 0)" "Scope x1" "Improved Energy Cell x1" \
  "ctl: LB_ITEMS in upgradeitems .* centre 518 220 .* rows 3 " "^where [0-9]* k2 carth " "LBL_UPGRADE_COUNT .* text '2'" "LBL_UPGRADE_COUNT .* text '1'" \
  "item view w_Blstrrfl_005 on camerahook4 (rotatehook4), shown"
expect bench_saber  module:ebo_m12aa bench_saber.txt   400 "assembled, upgrades 2 (were 0)" "Crystal, Blue x1" "tag g_w_lghtsbr02" \
  "the saber is now g_w_lghtsbr02" "item view w_Lghtsbr_002 on camerahook41 (turned by the panel), shown"
expect bench_dual   module:ebo_m12aa bench_dual.txt    350 "Sanasiki's Blade assembled, upgrades 8192" "Prototype Vibroblade assembled, upgrades 16384"
expect bench_armour module:ebo_m12aa bench_armour.txt  280 "assembled, upgrades 3145728 (were 0)" "worn 1: .* Eriadu Prototype Armor" \
  "item view PMBDM on camerahook32 (turned by the panel), shown"

if [ "$fails" -eq 0 ]; then echo "all item checks passed"; else echo "$fails item checks failed"; exit 1; fi
