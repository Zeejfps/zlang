#!/bin/sh
# Keeps the newest manual save of the Korriban runs as a checkpoint: sh kotor/tools/playthrough/korriban/ckpt.sh NAME
# (the script's `save` line wrote it to kotor/out/pt/saves_kor; CKPT=NAME loads it in the next part).
saves=${SAVES:-kotor/out/pt/saves_kor}
newest=$(ls "$saves" | grep ' - Game' | sort | tail -1)
if [ -z "$newest" ]; then echo "no save in $saves"; exit 1; fi
rm -rf "kotor/out/pt/kor_ckpt/$1"
mkdir -p kotor/out/pt/kor_ckpt
cp -r "$saves/$newest" "kotor/out/pt/kor_ckpt/$1"
echo "$1 <- $newest"
