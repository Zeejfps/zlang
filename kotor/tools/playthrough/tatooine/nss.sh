#!/bin/sh
# Extracts the NWScript sources the install ships for Tatooine (k_ptat*, tat*, k_trg_calo*, k_hmis*, k_con_*) into
# kotor/out/nss/ (git-ignored), so a quest's rules can be read: grep -l tat_KraytMap kotor/out/nss/*.nss.
# Run from the repository root; needs kotor/out/resls.exe.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
mkdir -p kotor/out/nss
cd kotor/out/nss || exit 1
for pat in 'k_ptat*' 'tat*' 'k_trg_calo*' 'k_hmis*' 'k_con_*' 'k_act_*' 'k_def_*'; do
  for n in $(../resls.exe --type nss "$pat" | grep '\.nss' | cut -f1); do
    [ -f "$n" ] || ../resls.exe get "$n" > /dev/null
  done
done
ls | wc -l
