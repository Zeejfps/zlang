#!/bin/sh
# Pictures of four scenes at five window sizes (docs/mechanics/graphics.md, "Checking it"): the main menu, the HUD in the
# Taris apartment, the opening conversation's reply list, and an in-game panel (the character sheet). Hidden windows take
# any size, so this runs headless. Needs the checkpoints (sh kotor/tools/checkpoints/make.sh).
#
#   sh kotor/tools/gfx/sizes.sh [EXE]            (from the repository root; EXE defaults to kotor/out/kotor.exe)
#
# Writes kotor/out/gfx/sizes/SCENE_WxH.png, and a contact sheet per scene (sizes.py).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${1:-kotor/out/kotor.exe}
out=kotor/out/gfx/sizes
mkdir -p $out kotor/out/gfx/saves_sizes
printf '5 ui menu character\n' > $out/panel.txt
for size in 1280x720 1920x1080 2560x1440 3840x2160 2560x1080; do
  common="--headless --size $size --saves kotor/out/gfx/saves_sizes"
  $exe $common --frames 100 --screenshot-at 90:$out/menu_$size.png > /dev/null 2>&1
  $exe $common --load kotor/out/checkpoints/apartment --frames 40 --screenshot-at 30:$out/hud_$size.png > /dev/null 2>&1
  $exe $common --module end_m01aa --frames 800 --screenshot-at 795:$out/dialogue_$size.png > /dev/null 2>&1
  $exe $common --load kotor/out/checkpoints/apartment --input $out/panel.txt --frames 60 --screenshot-at 50:$out/panel_$size.png > /dev/null 2>&1
  echo "$size done"
done
