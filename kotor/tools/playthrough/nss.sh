#!/bin/sh
# Extracts the NWScript sources the install ships whose names match the patterns into kotor/out/nss/ (git-ignored), so a quest's
# rules can be read: sh kotor/tools/playthrough/nss.sh 'k_plev*' 'lev*'; grep -l LEV_ kotor/out/nss/*.nss.
# Run from the repository root; needs kotor/out/resls.exe.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
mkdir -p kotor/out/nss
cd kotor/out/nss || exit 1
for pat in "$@"; do
  for n in $(../resls.exe --type nss "$pat" | grep '\.nss' | cut -f1); do
    [ -f "$n" ] || ../resls.exe get "$n" > /dev/null
  done
done
ls | wc -l
