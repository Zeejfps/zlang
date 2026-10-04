#!/bin/sh
# Disassembles the scripts of every Tatooine module into kotor/out/ncs/NAME.txt (once each), so
# `grep -l ROUTINE kotor/out/ncs/*.txt` says who calls what. Run from the repository root; needs
# kotor/out/resls.exe and ncsdis.exe (docs/playthrough.md, ncsgrep.sh).
for m in tat_m17aa tat_m17ab tat_m17ac tat_m17ad tat_m17ae tat_m17af tat_m17ag tat_m18aa tat_m18ab tat_m18ac tat_m20aa; do
  sh kotor/tools/playthrough/ncsgrep.sh $m
done
