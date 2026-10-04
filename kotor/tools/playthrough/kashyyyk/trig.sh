#!/bin/sh
# The world-space outline of a trigger of a module's area, and its enter script:
#
#   sh kotor/tools/playthrough/kashyyyk/trig.sh MODULE TAG        e.g.  kas_m22ab kas22_sithattk
#
# The area file is the module name without its prefix (kas_m22ab -> m22ab). The geometry points are relative to the trigger's
# position; this prints them added to it, so a test can aim a walk (`goto X,Y`) at the inside of a thin trigger.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
module=$1
tag=$2
area=$(echo "$module" | sed 's/^[a-z]*_//')
kotor/out/gffdump.exe --module "$module" "$area.git" > kotor/out/pt/_area_$area.txt
n=$(grep -n "TemplateResRef: CResRef = \"$tag\"" kotor/out/pt/_area_$area.txt | head -1 | cut -d: -f1)
if [ -z "$n" ]; then echo "no $tag"; exit 1; fi
sed -n "$n,$((n+40))p" kotor/out/pt/_area_$area.txt | awk '
  /XPosition/ { px = $NF } /YPosition/ { py = $NF }
  /PointX/ { x = $NF } /PointY/ { printf "point %.2f,%.2f\n", px + x, py + $NF }
  /TemplateResRef/ { if (seen++) exit }
  END { printf "at %s,%s\n", px, py }'
kotor/out/gffdump.exe --module "$module" "$tag.utt" | grep "ScriptOnEnter\|ScriptOnExit"
