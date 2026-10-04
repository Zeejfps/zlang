#!/bin/sh
# Replays the Tatooine playthrough part after part, each from the checkpoint the one before wrote:
#
#   sh kotor/tools/playthrough/tatooine/all.sh [FIRST_PART]        (run from the repository root; about 25 minutes)
#
# Needs kotor/out/kotor_tat.exe (kotor/tools/ctxc exe kotor -o kotor/out/kotor_tat.exe). The logs are kotor/out/pt/tN.log,
# the checkpoints kotor/out/tat_cp/NAME (a part's `save` line writes them, keep.sh copies the newest). Starting at a later part
# reuses the checkpoints already there. docs/playthrough-tatooine.md says what each part does and where the chain stops.
d=kotor/tools/playthrough/tatooine
first=${1:-1}
export LOG=${LOG:-dialog}
export TIMEOUT=${TIMEOUT:-1500}

step() {   # PART SCRIPT FRAMES CKPT_IN CKPT_OUT
  part=$1; script=$2; frames=$3; from=$4; to=$5
  if [ "$part" -lt "$first" ]; then return; fi
  if [ -n "$from" ]; then
    LOAD=kotor/out/tat_cp/$from sh $d/run.sh t$part $d/$script $frames
  else
    sh $d/run.sh t$part $d/$script $frames -- --module tat_m17ab
  fi
  sh $d/keep.sh $to
}

if [ "$first" -le 1 ]; then rm -rf kotor/out/saves_tat; fi
step 1  01_dock.txt    5800  ""        anchor
step 2  02_office.txt  4300  anchor    office
step 3  03_hk47.txt    15000 office    hk47
step 4  04_gate.txt    3950  hk47      dune
step 5  05_dune.txt    11200 dune      strip
step 6  06_loot.txt    900   strip     disguised
step 7  07_chief.txt   9600  disguised vapor
step 8  08_vapor.txt   16100 vapor     vapors
step 9  09_peace.txt   19100 vapors    peace
step 10 10_krayt.txt   5700  peace     east
step 11 11_komad.txt   13100 east      komad1
step 12 12_fodder.txt  5600  komad1    fodder
step 13 13_bantha.txt  7100  fodder  komad2
step 14 14_herd.txt    9000  komad2  herd
step 15 15_lead.txt    3300  herd    dragon
step 16 16_cave.txt    3100  dragon  starmap
step 17 17_calo.txt    6100  starmap calo
step 18 18_back.txt    9100  calo    czerka
step 19 19_hawk.txt    1000  czerka  hawk
step 20 20_travel.txt  8000  hawk    kas_arrival
