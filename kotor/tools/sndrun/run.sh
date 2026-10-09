#!/bin/sh
# The game's sound at real pace, measured without speakers (docs/testing.md; docs/design/audio.md, "Checked").
#
#   EXE=kotor/out/kotor.exe [CK=kotor/out/checkpoints] sh kotor/tools/sndrun/run.sh [ES_FRAMES]
#
# Two runs, headless with the sound device open on SDL's disk driver (which takes the samples at the
# speakers' pace and writes them to a file) and every pass held to the 1/30 s step (--sound-device):
#   fight  the Upper City checkpoint, Carth and the leader against six Sith troopers (fight6.txt, 1,800 frames, 1 min)
#   es     the Endar Spire replay from New Game, ES_FRAMES frames (default 6000, about 4 min: the bunk room's
#          loops, Trask, the first corridor fights)
# Each run's `--log sound` summary and its recording (kotor/tools/py/sndscan.py) are checked; FAIL (exit 1) when
# a voice was stolen from a sound as important as the new one, the device ran dry after a frame under 60 ms (past the
# first second), or more than 1,000 samples were clipped. Underruns after slower frames and the recording's dropouts
# and clicks are printed: they depend on how busy the machine is. Logs and recordings in kotor/out/sndrun/.
py=$(command -v python)                         # Windows' Python (numpy), found before MSYS2's comes first on PATH
export PATH=/g/Dev/msys64/mingw64/bin:$PATH     # SDL2.dll
exe=${EXE:-kotor/out/kotor.exe}
ck=${CK:-kotor/out/checkpoints}
out=kotor/out/sndrun
mkdir -p $out
fail=0

check() {
  name=$1
  log=$out/$name.log
  "$py" kotor/tools/py/sndscan.py $out/$name.raw --list 3 > $out/$name.scan.txt
  summary=$(grep -a '^sound mixer:' $log)
  if [ -z "$summary" ]; then echo "FAIL $name: no sound summary (see $log)"; fail=1; return; fi
  steals=$(echo "$summary" | awk '{ print $3 }')
  clipped=$(echo "$summary" | awk -F', ' '{ for (i = 1; i <= NF; i++) if ($i ~ /samples clipped/) { split($i, w, " "); print w[1] } }')
  # The device running dry after a frame quicker than 60 ms (past the first second) is the queue's fault, not the frame's.
  quick=$(grep -a 'sound underrun' $log | awk '{ f = substr($1, 2) + 0; split($0, p, "after a "); if (f > 30 && p[2] + 0 < 60) n++ } END { print n + 0 }')
  echo "     $name: $summary"
  echo "     $name: $(grep -a '^dropouts:' $out/$name.scan.txt); $(grep -a '^clicks:' $out/$name.scan.txt)"
  if [ "$steals" -gt 0 ] || [ "$quick" -gt 0 ] || [ "$clipped" -gt 1000 ]; then
    echo "FAIL $name: $steals steals, $quick underruns after a frame under 60 ms, $clipped samples clipped"
    fail=1
  else
    echo "ok   $name"
  fi
}

if [ -d $ck/uppercity ]; then
  rm -rf $out/saves
  SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=$out/fight.raw timeout 600 $exe --headless --sound-device --load $ck/uppercity \
    --saves $out/saves --input kotor/tools/sndrun/fight6.txt --frames 1800 --log sound > $out/fight.log 2>&1
  check fight
else
  echo "skip fight: no checkpoint $ck/uppercity (sh kotor/tools/checkpoints/make.sh)"
fi
rm -rf $out/saves
SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=$out/es.raw timeout 900 $exe --headless --sound-device \
  --saves $out/saves --input kotor/tools/playthrough/10_endar_spire.txt --frames ${1:-6000} --log sound > $out/es.log 2>&1
check es
exit $fail
