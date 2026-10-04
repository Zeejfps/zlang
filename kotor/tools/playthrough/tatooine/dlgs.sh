#!/bin/sh
# The conversations of every Tatooine module (name only), one module a line. Run from the repository root.
for m in tat_m17aa tat_m17ab tat_m17ac tat_m17ad tat_m17ae tat_m17af tat_m17ag tat_m18aa tat_m18ab tat_m18ac tat_m20aa; do
  echo "== $m: $(kotor/out/resls.exe --module $m --type dlg | cut -f1 | sed 's/\.dlg//' | grep -v '^k_h\|^banter\|^g_\|^k_gen\|^k_trans\|^ptar\|^tar02' | tr '\n' ' ')"
done
