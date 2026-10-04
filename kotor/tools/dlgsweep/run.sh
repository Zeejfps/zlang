#!/bin/sh
# The conversation sweep: every DLG of the install walked node by node with its scripts run, one
# fresh process each, in parallel, and one table in kotor/docs/dlgsweep.md.
#
#   sh kotor/tools/dlgsweep/run.sh [-j JOBS] [-o OUTDIR] [-r] [MODULE...]     (from the repository root)
#
# Pass 1 lists, for each module, the dialogues its archive holds and the ones its objects name, then
# sweeps each in a freshly entered copy of the module with the object that names it as the owner (a
# stand-in creature if none does). Pass 2 sweeps the dialogues no module's archive holds and no object
# named, in end_m01aa, with a stand-in as the owner. MODULE... limits the run to those modules (the
# table then goes to OUTDIR/dlgsweep.md and pass 2 is skipped). -r rebuilds the table from OUTDIR's
# logs. Environment: EXE (kotor/out/dlgsweep.exe, built here), TIMEOUT (300 s a process).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
here=$(dirname "$0")
jobs=${NUMBER_OF_PROCESSORS:-8}
OUT=kotor/out/dlgsweep
report_only=
while [ $# -gt 0 ]; do
  case "$1" in
    -j) jobs=$2; shift 2 ;;
    -o) OUT=$2; shift 2 ;;
    -r) report_only=1; shift ;;
    *) break ;;
  esac
done
EXE=${EXE:-kotor/out/dlgsweep.exe}
export OUT EXE
mkdir -p "$OUT"
if [ -z "$report_only" ]; then
  kotor/tools/ctxc exe kotor/tools/dlgsweep -o "$EXE" || exit 1
  rm -rf "$OUT/modules" "$OUT/pairs" "$OUT"/*.txt
  mkdir -p "$OUT/modules" "$OUT/pairs"
  if [ $# -gt 0 ]; then list="$*"; else list=$(sh kotor/tools/smoke/modules.sh); fi
  start=$(date +%s)
  echo "listing $(echo $list | wc -w) modules, $jobs at a time..."
  echo $list | tr ' ' '\n' | xargs -P "$jobs" -n 1 sh "$here/one.sh"
  # MODULE DLG, a line each.
  for m in $list; do
    grep -a '^CAND ' "$OUT/modules/$m.log" | cut -d ' ' -f 2 | sed "s/^/$m /"
  done > "$OUT/pairs.txt"
  if [ $# -eq 0 ]; then
    # The global dialogues nothing named.
    "$EXE" --list-global | tr 'A-Z' 'a-z' | sort -u > "$OUT/global.txt"
    cut -d ' ' -f 2 "$OUT/pairs.txt" | tr 'A-Z' 'a-z' | sort -u > "$OUT/named.txt"
    comm -23 "$OUT/global.txt" "$OUT/named.txt" | sed 's/^/end_m01aa /' >> "$OUT/pairs.txt"
  fi
  echo "sweeping $(grep -c '' "$OUT/pairs.txt") dialogues..."
  xargs -P "$jobs" -L 1 sh "$here/one.sh" < "$OUT/pairs.txt"
  echo "swept in $(( $(date +%s) - start )) s"
fi
if [ $# -gt 0 ]; then dest="$OUT/dlgsweep.md"; else dest=kotor/docs/dlgsweep.md; fi
sh "$here/report.sh" "$OUT" > "$dest"
echo "table: $dest"
