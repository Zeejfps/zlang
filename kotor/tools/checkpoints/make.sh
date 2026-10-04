#!/bin/sh
# Makes the checkpoints: saves written at milestones of the Endar Spire replay, so a test can start there
# (kotor --load kotor/out/checkpoints/NAME) instead of replaying from New Game, and for each a resume
# script: the rest of the replay, from that point on.
#
#   sh kotor/tools/checkpoints/make.sh [REPLAY]        (run from the repository root; REPLAY defaults to
#                                                       kotor/tools/playthrough/10_endar_spire.txt)
#
# Writes kotor/out/checkpoints/NAME/ (a save folder) and NAME.txt (the resume script) for each NAME below,
# kotor/out/checkpoints/make.log (the replay's log) and work/ (its scratch saves). It plays the replay
# with --no-render --speed 8, which logs what the plain headless run does (docs/design/engine.md),
# in a minute or two. The frames are those of the 1/30 s headless run: when the engine's timing of a
# cutscene or a voice changes they shift, and the replay's own lines (docs/playthrough.md) do too.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
replay=${1:-kotor/tools/playthrough/10_endar_spire.txt}
exe=${EXE:-kotor/out/kotor.exe}
out=kotor/out/checkpoints

# name:frame. Each frame is between two of the replay's steps, with no menu open and no conversation up.
points="bunk:3940 bridge:13950 pod:31900 apartment:39450 uppercity:40450 cantina:56800 lowercity:65000 undercity:70400 mission:74000 gate:77300 sithbase:79900"

rm -rf $out/work
mkdir -p $out/work/saves
# The replay with a bot status and a save at each checkpoint's frame, in frame order (a stable sort).
{
  grep -v '^#' "$replay" | grep -v '^[[:space:]]*$'
  for p in $points; do
    echo "${p#*:} ui bot status"
    echo "${p#*:} save ${p%%:*}"
  done
} | sort -s -n -k1,1 > $out/work/input.txt
last=0
for p in $points; do last=${p#*:}; done
last=$((last + 10))

echo "replaying $last frames..."
$exe --no-render --speed 8 --frames $last --input $out/work/input.txt --saves $out/work/saves --log dialog > $out/make.log 2>&1
echo "replay exit $?, $(grep -a -c '' $out/make.log) log lines, $(grep -a -c '^fault:' $out/make.log) faults"

# The manual saves, oldest first, are the checkpoints in frame order.
saves=$(ls $out/work/saves | grep ' - Game' | sort)
i=0
for p in $points; do
  name=${p%%:*}
  frame=${p#*:}
  i=$((i + 1))
  folder=$(echo "$saves" | sed -n "${i}p")
  if [ -z "$folder" ]; then echo "$name: no save was written at frame $frame"; continue; fi
  rm -rf "$out/$name"
  cp -r "$out/work/saves/$folder" "$out/$name"

  # Where the replay's bot stood at the checkpoint: its n-th status line, n counting the replay's own
  # `ui bot status` lines before this frame and this checkpoint's.
  n=$(awk -v f="$frame" '$2 == "ui" && $3 == "bot" && $4 == "status" && ($1 + 0) <= f { c++ } END { print c + 0 }' $out/work/input.txt)
  stop=$(grep -a '^bot: [0-9]* stops, at ' $out/make.log | sed -n "${n}p" | sed -n 's/.* at \([0-9]*\).*/\1/p')
  # Replies the conversations of the replay had used up by then (the `ui replies` queue).
  used=$(awk -v f="$frame" '/^\[[0-9]+ / { fr = substr($1, 2) + 0; if (fr <= f && /dialog scripted reply/) c++ } END { print c + 0 }' $out/make.log)

  # The resume script: what the replay's setup lines (reply queue, bot cheats and route) amount to at the
  # checkpoint, then every later line of the replay, its frame counted from the load.
  awk -v f="$frame" -v used="${used:-0}" -v stop="${stop:-0}" -v name="$name" '
    /^#/ || NF == 0 { next }
    {
      fr = $1 + 0
      if (fr > f) { later[++nl] = (fr - f) " " substr($0, index($0, $2)); next }
      if ($2 == "ui" && $3 == "replies") { nrep = 0; for (k = 4; k <= NF; k++) rep[++nrep] = $k }
      if ($2 == "ui" && $3 == "bot") {
        if ($4 == "route") { nstop = 0; for (k = 5; k <= NF; k++) stp[++nstop] = $k }
        else if ($4 == "on") on = 1
        else if ($4 == "off") on = 0
        else if ($4 == "god") god = ($5 == "off") ? 0 : 1
        else if ($4 == "unlock") unlock = ($5 == "off") ? 0 : 1
        else if ($4 == "party") party = ($5 == "off") ? 0 : 1
      }
    }
    END {
      print "# Resume of " FILENAME " from checkpoint " name " (frame " f "): kotor --load kotor/out/checkpoints/" name " --input this file"
      line = ""
      for (k = used + 1; k <= nrep; k++) line = line " " rep[k]
      if (line != "") print "1 ui replies" line
      if (god) print "1 ui bot god on"
      if (unlock) print "1 ui bot unlock on"
      if (party) print "1 ui bot party on"
      if (nstop > 0 && stop < nstop) {
        line = ""
        for (k = stop + 1; k <= nstop; k++) line = line " " stp[k]
        print "1 ui bot route" line
      }
      if (on) print "2 ui bot on"
      for (k = 1; k <= nl; k++) print later[k]
    }' "$replay" > "$out/$name.txt"
  echo "$name: frame $frame, save '$folder', bot at stop ${stop:-?}, $used replies used, $(grep -c '' "$out/$name.txt") resume lines"
done
