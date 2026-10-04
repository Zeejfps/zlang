#!/bin/sh
# Which modules hold an object whose tag contains PART, and where: sh kotor/tools/playthrough/wheremod.sh PART [MODULE...]
# (every Taris module when none is given; each loads for 30 frames headless)
part=$1
shift
mods="$*"
if [ -z "$mods" ]; then
  mods="tar_m02aa tar_m02ab tar_m02ac tar_m02ad tar_m02ae tar_m02af tar_m03aa tar_m03ab tar_m03ad tar_m03ae tar_m03af tar_m04aa tar_m05aa tar_m05ab tar_m08aa tar_m09aa tar_m09ab tar_m10aa tar_m10ab tar_m10ac tar_m11aa tar_m11ab"
fi
echo "5 ui where $part" > kotor/out/pt/wheremod.txt
for m in $mods; do
  FAST=1 sh kotor/tools/playthrough/run.sh wheremod kotor/out/pt/wheremod.txt 30 -- --module $m > /dev/null
  echo "$m: $(grep -a '^where' kotor/out/pt/wheremod.log | cut -c1-90 | tr '\n' ';')"
done
