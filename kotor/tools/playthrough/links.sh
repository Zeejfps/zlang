#!/bin/sh
# The transitions of the modules: which door or trigger of MODULE leads to which module and waypoint.
#   sh kotor/tools/playthrough/links.sh tar_m02aa tar_m02ac ...
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
for m in "$@"; do
  area=$(echo "$m" | sed 's/^[a-z]*_//')
  echo "== $m"
  kotor/out/gffdump.exe --module "$m" "$area.git" | grep -a -B6 "LinkedToModule: CResRef = \"[a-z]" | grep -a "Tag:\|LinkedToModule\|LinkedTo:\|TemplateResRef" | paste -sd' ' | sed 's/ Tag:/\nTag:/g' | sed 's/CExoString = //; s/CResRef = //' | grep -a LinkedToModule
done
