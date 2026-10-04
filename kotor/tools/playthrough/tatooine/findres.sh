#!/bin/sh
# Which resources of the Tatooine modules mention a word (an item resref, a tag, a script): GFF resources (utc utp utm uti git
# dlg are, ute utt utw) are dumped and searched. Run from the repository root; needs kotor/out/resls.exe and gffdump.exe.
#
#   sh kotor/tools/playthrough/tatooine/findres.sh WORD [MODULE...]      (default: every Tatooine module)
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
word=$1
shift
mods="$*"
if [ -z "$mods" ]; then mods="tat_m17aa tat_m17ab tat_m17ac tat_m17ad tat_m17ae tat_m17af tat_m17ag tat_m18aa tat_m18ab tat_m18ac tat_m20aa"; fi
for m in $mods; do
  for t in utc utp utm uti git dlg ute utt utw are; do
    for n in $(kotor/out/resls.exe --module $m --type $t | grep 'rim\|mod' | cut -f1); do
      if kotor/out/gffdump.exe --module $m $n 2>/dev/null | grep -q -i "$word"; then echo "$m $n"; fi
    done
  done
done
