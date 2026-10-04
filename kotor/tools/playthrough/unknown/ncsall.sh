#!/bin/sh
# Disassembles the scripts of every module of the Unknown World and the Star Forge into kotor/out/ncs/NAME.txt (once each). Run from the repository root.
for m in ebo_m41aa unk_m41aa unk_m41ab unk_m41ac unk_m41ad unk_m42aa unk_m43aa unk_m44aa unk_m44ab unk_m44ac sta_m45aa sta_m45ab sta_m45ac sta_m45ad; do
  sh kotor/tools/playthrough/ncsgrep.sh $m > /dev/null
done
ls kotor/out/ncs | wc -l
