#!/bin/sh
# The story lines of a run's log: sh kotor/tools/playthrough/manaan/lg.sh NAME [FROM_FRAME] [EXTRA_GREP_V_REGEX]
# Drops the idle scripts, the stage dumps and the per-frame picture lines; keeps conversations, journal, XP, combat, faults.
name=$1
from=${2:-0}
extra=${3:-NOMATCHATALL}
awk -v from="$from" '/^\[/{f=substr($1,2)+0; if(f<from)next} {print}' kotor/out/pt/$name.log |
  grep -v -E '^(where|  portrait|  door|  )|frame [0-9]+: wrote|^  (frame|sun|leader)|k_pman_ambient|k_def_heartbt|k_def_percept|k_ai_master|k_def_spawn|k_def_userdef|k_pman_amb_9|k_hen_|k_pman_rapid|^jedi:|dialog view|dialog voice|dialog condition|dialog entry script' |
  grep -v -E "$extra" | cut -c1-${WIDTH:-230}
