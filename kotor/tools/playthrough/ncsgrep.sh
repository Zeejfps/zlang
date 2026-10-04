#!/bin/sh
# Disassembles every script a module can see into kotor/out/ncs/NAME.txt (once), so
# `grep -l ROUTINE kotor/out/ncs/*.txt` says which scripts call a routine.
#
#   sh kotor/tools/playthrough/ncsgrep.sh MODULE          (build kotor/tools/ncsdis and resls to kotor/out/*.exe first)
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
module=$1
mkdir -p kotor/out/ncs
kotor/out/resls.exe --module "$module" --type ncs > kotor/out/ncs/_list.txt
for n in $(cut -d. -f1 kotor/out/ncs/_list.txt | cut -d' ' -f1); do
  if [ ! -f kotor/out/ncs/$n.txt ]; then
    kotor/out/ncsdis.exe "$n" --module "$module" > kotor/out/ncs/$n.txt 2>/dev/null
  fi
done
ls kotor/out/ncs | wc -l
