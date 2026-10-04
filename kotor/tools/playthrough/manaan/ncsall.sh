#!/bin/sh
# Disassembles every script the Manaan modules can see into kotor/out/ncs (once each), so grep -l ROUTINE kotor/out/ncs/*.txt
# says which scripts call what. Run from the repository root; needs kotor/out/resls.exe and ncsdis.exe (docs/testing.md).
for m in manm26aa manm26ab manm26ac manm26ad manm26ae manm27aa manm28aa manm28ab manm28ac manm28ad; do
  sh kotor/tools/playthrough/ncsgrep.sh $m | tail -1
done
