#!/bin/sh
# Makes the checkpoints after sithbase, which come from the story scripts rather than the Endar Spire replay:
# 40_sithbase.txt saves `vulkar`, 43_elevator.txt `garage`, 44_kandon.txt `kandon`, 45_gadon.txt `swoop`, and so
# on. Each step loads the checkpoint before it, plays its script to the save and copies the save to
# kotor/out/checkpoints/NAME (so it needs make.sh's sithbase first).
#
#   sh kotor/tools/checkpoints/chain.sh [FIRST_NAME]       (run from the repository root; FIRST_NAME resumes the chain there)
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${EXE:-kotor/out/kotor.exe}
out=kotor/out/checkpoints
pt=kotor/tools/playthrough
first=${1:-vulkar}
started=
# name : loaded checkpoint : script : frames : index of the script's manual save that is the checkpoint
steps="vulkar:sithbase:40_sithbase:18000:2 garage:vulkar:43_elevator:27500:1 kandon:garage:44_kandon:19000:1 swoop:kandon:45_gadon:19500:1 apt:swoop:46_race:22100:1 cand:apt:47_canderous:19700:1 t3:cand:48_t3:6600:1 codes:t3:49_sithbase:13600:1"
for s in $steps; do
  name=${s%%:*}; rest=${s#*:}
  from=${rest%%:*}; rest=${rest#*:}
  script=${rest%%:*}; rest=${rest#*:}
  frames=${rest%%:*}; idx=${rest#*:}
  if [ "$name" = "$first" ]; then started=1; fi
  if [ -z "$started" ]; then continue; fi
  saves=$out/work_$name
  rm -rf $saves; mkdir -p $saves
  $exe --no-render --speed 8 --frames $frames --input $pt/$script.txt --load $out/$from --saves $saves --log dialog > $out/$name.log 2>&1
  folder=$(ls $saves | grep ' - Game' | sort | sed -n "${idx}p")
  if [ -z "$folder" ]; then echo "$name: no save"; continue; fi
  rm -rf $out/$name
  cp -r "$saves/$folder" $out/$name
  echo "$name: from $from, save '$folder', $(grep -a -c '^fault:' $out/$name.log) faults"
done
