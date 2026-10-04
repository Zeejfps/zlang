#!/bin/sh
# The module smoke test: every module of the install, started headless with a default party and left
# running for 60 s of world time, in parallel (one process per core), then one table in kotor/docs/smoke.md.
#
#   sh kotor/tools/smoke/run.sh [-j JOBS] [-o OUTDIR] [-r] [MODULE...]     (run from the repository root)
#
# MODULE... limits the run to those modules (the table is then written to OUTDIR/smoke.md, not the docs).
# -j: processes at once (default: the cores); -r: only rebuild the table from OUTDIR's logs. Environment:
# FRAMES (ticks of 1/30 s per run, default 1800), EXE (kotor/out/kotor.exe), GAME (the install),
# TIMEOUT (seconds a run may take, 180).  The pieces: modules.sh, one.sh (a run), report.sh (the table).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
here=$(dirname "$0")
jobs=${NUMBER_OF_PROCESSORS:-8}
OUT=kotor/out/smoke
report_only=
while [ $# -gt 0 ]; do
  case "$1" in
    -j) jobs=$2; shift 2 ;;
    -o) OUT=$2; shift 2 ;;
    -r) report_only=1; shift ;;
    *) break ;;
  esac
done
export OUT
mkdir -p "$OUT"
if [ -z "$report_only" ]; then
  rm -f "$OUT"/*.log "$OUT"/*.meta "$OUT"/*.probe
  if [ $# -gt 0 ]; then list="$*"; else list=$(sh "$here/modules.sh"); fi
  count=$(echo $list | wc -w)
  start=$(date +%s)
  echo "$count modules, $jobs at a time..."
  echo $list | tr ' ' '\n' | xargs -P "$jobs" -n 1 sh "$here/one.sh"
  echo "ran in $(( $(date +%s) - start )) s"
fi
if [ $# -gt 0 ]; then dest="$OUT/smoke.md"; else dest=kotor/docs/smoke.md; fi
sh "$here/report.sh" "$OUT" > "$dest"
echo "table: $dest"
