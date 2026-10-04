#!/bin/sh
# Makes the checkpoints after sithbase, which come from the story scripts rather than the Endar Spire replay:
# 40_sithbase.txt saves `vulkar`, 43_elevator.txt `garage`, 44_kandon.txt `kandon`, 45_gadon.txt `swoop`, and so
# on. Each step loads the checkpoint before it, plays its script to the save and copies the save to
# kotor/out/checkpoints/NAME (so it needs make.sh's sithbase first).
#
#   sh kotor/tools/checkpoints/chain.sh [FIRST_NAME]       (run from the repository root; FIRST_NAME resumes the chain there)
#
# The scripts' fights depend on the dice and the timing, so a `save` line at a fixed frame can fall in the wrong place after
# an engine change: a step names the module its save must be in, and the script says so when it is not ("WRONG MODULE").
# `savewhen MODULE NAME` in a script saves once the story has been quiet in MODULE for 2 s, whatever frame that is.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${EXE:-kotor/out/kotor.exe}
out=kotor/out/checkpoints
pt=kotor/tools/playthrough
first=${1:-vulkar}
started=
# name : loaded checkpoint : script : frames : index of the script's manual save that is the checkpoint : its module
steps="vulkar:sithbase:40_sithbase:22000:1:tar_m10aa garage:vulkar:43_elevator:30000:1:tar_m10ac kandon:garage:44_kandon:20000:1:tar_m10ac swoop:kandon:45_gadon:30000:1:tar_m03af apt:swoop:46_race:24000:1:tar_m02af cand:apt:47_canderous:21000:1:tar_m03ae t3:cand:48_t3:7000:1:tar_m02ab codes:t3:49_sithbase:20000:1:tar_m09ab davik:codes:50_codes:26000:1:tar_m08aa"
for s in $steps; do
  name=${s%%:*}; rest=${s#*:}
  from=${rest%%:*}; rest=${rest#*:}
  script=${rest%%:*}; rest=${rest#*:}
  frames=${rest%%:*}; rest=${rest#*:}
  idx=${rest%%:*}; module=${rest#*:}
  if [ "$name" = "$first" ]; then started=1; fi
  if [ -z "$started" ]; then continue; fi
  saves=$out/work_$name
  rm -rf $saves; mkdir -p $saves
  $exe --no-render --speed 8 --frames $frames --input $pt/$script.txt --load $out/$from --saves $saves --log dialog > $out/$name.log 2>&1
  folder=$(ls $saves | grep ' - Game' | sort | sed -n "${idx}p")
  if [ -z "$folder" ]; then echo "$name: no save"; continue; fi
  rm -rf $out/$name
  cp -r "$saves/$folder" $out/$name
  rm -rf $out/work_verify; mkdir -p $out/work_verify
  where=$($exe --load $out/$name --no-render --frames 2 --saves $out/work_verify --log module 2>&1 | grep -a '^\[.*loaded ' | sed 's/.*(\(.*\))$/\1/')
  if [ "$where" = "$module" ]; then ok="in $module"; else ok="WRONG MODULE: in '$where', expected $module"; fi
  echo "$name: from $from, save '$folder', $ok, $(grep -a -c '^fault:' $out/$name.log) faults"
done
