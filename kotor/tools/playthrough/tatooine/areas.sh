#!/bin/sh
# The name of each Tatooine module's area, and its Mod_Entry_Area / entry point. Run from the repository root.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
for m in m17aa m17ab m17ac m17ad m17ae m17af m17ag m17mg m18aa m18ab m18ac m20aa; do
  echo "== $m: $(kotor/out/gffdump.exe --module tat_$m $m.are 2>&1 | grep -i -m2 'Name' | tr '\n' ' ' | cut -c1-200)"
done
