#!/bin/sh
# The conversations of every module of the Unknown World and the Star Forge (name only), one module a line. Run from the repository root.
for m in ebo_m41aa unk_m41aa unk_m41ab unk_m41ac unk_m41ad unk_m42aa unk_m43aa unk_m44aa unk_m44ab unk_m44ac sta_m45aa sta_m45ab sta_m45ac sta_m45ad; do
  echo "== $m: $(kotor/out/resls.exe --module $m --type dlg | cut -f1,4 | grep "$m" | cut -f1 | sed 's/\.dlg//' | tr '\n' ' ')"
done
