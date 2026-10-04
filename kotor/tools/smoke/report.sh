#!/bin/sh
# The smoke test's table, as markdown on standard output, from a run's logs.   sh report.sh OUTDIR
# (OUTDIR holds MODULE.log, MODULE.meta and MODULE.probe from one.sh.)
out=${1:-kotor/out/smoke}
tab=$(printf '\t')
tmp=$out/table.tsv
rm -f "$out/details.tsv.new"
frames=${FRAMES:-18000}

# One line a module: the fields the table sorts and prints.
for meta in "$out"/*.meta; do
  m=$(basename "$meta" .meta)
  log=$out/$m.log
  probe=$out/$m.probe
  [ -f "$probe" ] || probe=/dev/null
  awk -v m="$m" -v meta="$(cat "$meta")" -v probe="$probe" '
    BEGIN {
      split(meta, mt, " "); rc = mt[1] + 0; wall = mt[2] + 0
      # a stuck action is the same action, in the same place, a further 10 s of world time on
      while ((getline line < probe) > 0) { sub(/^stuck [0-9]+ /, "", line); n = split(line, f, " "); key = f[1] " " f[2] " " f[4] " " f[5] " " f[6]; later[key] = 1 }
    }
    /^frames: / { avg = $3; slow = $8 }
    /^run: / { world = $4 }
    /^bot: tour of / { tn = $4; tk = $7 + 0 }
    /^\[[0-9]+ [0-9.]+\] module [A-Za-z0-9_]+: area / {
      mod = tolower($4); sub(/:$/, "", mod)
      if (first == "") first = mod
      else if (mod != first && !(mod in seen)) { seen[mod] = 1; nwent++; if (nwent <= 3) went = went (nwent > 1 ? ", " : "") mod; else if (nwent == 4) went = went ", ..." }
    }
    /^scene: .*textures/ { s = $0; sub(/.*textures [0-9]+ loaded, /, "", s); sub(/ missing.*/, "", s); tex = s + 0 }
    /^routines called: / { }
    /^  missing / { miss++; calls += substr($4, 2) + 0; names[miss] = $3 "x" substr($4, 2) }
    /fault: / {
      line = $0; sub(/^.*fault: /, "", line)
      script = line; sub(/ .*/, "", script)
      rest = line; sub(/^[^:]*: /, "", rest); kind = rest; sub(/:.*/, "", kind)
      vm = (kind ~ /stack|opcode|past the end|nested|STORE_STATE|without|unbalanced|already running|wrong kind of reply/)
      if (vm) vmf++; else scf++
      detail[script " | " kind]++
    }
    /^kotor:|^visual [0-9]+ \(|^dialog panels:/ { loaderr++; lerr[loaderr] = $0 }
    /panic/ { if (panic == "") panic = $0 }
    /^stuck / { sub(/^stuck [0-9]+ /, "", $0); n = split($0, f, " "); key = f[1] " " f[2] " " f[4] " " f[5] " " f[6]; if (key in later) { stuck++; stuckname[stuck] = f[1] } }
    END {
      status = "ok"
      if (rc == 124) status = "timeout"; else if (rc != 0) status = "crash"
      if (panic != "") status = "crash"
      topm = ""
      for (i = 1; i <= miss && i <= 3; i++) topm = topm (i > 1 ? ", " : "") names[i]
      sn = ""
      for (i = 1; i <= stuck && i <= 3; i++) sn = sn (i > 1 ? ", " : "") stuckname[i]
      gsub(/\|/, "/", panic)
      printf "%s\t%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s\t%d\t%s\t%s\t%s\t%s\t%d\t%s\t%s\t%s\n", m, status, (status != "ok"), vmf + 0, scf + 0, loaderr + 0, calls + 0, stuck + 0, tex + 0, avg, wall, slow, topm, sn, substr(panic, 1, 120), miss + 0, world, (tn > 0 ? tk "/" tn : "-"), (went != "" ? went : "-")
      for (k in detail) printf "D\t%s\t%s\t%d\n", m, k, detail[k] > "/dev/stderr"
      for (i = 1; i <= loaderr && i <= 3; i++) printf "L\t%s\t%s\n", m, lerr[i] > "/dev/stderr"
    }' "$log" 2>> "$out/details.tsv.new"
done > "$tmp.unsorted"
# worst first: crashes, VM faults, script faults, load errors, missing routine calls, stuck, textures, then time
sort -t "$tab" -k3,3nr -k4,4nr -k5,5nr -k6,6nr -k7,7nr -k8,8nr -k9,9nr -k10,10nr -k1,1f "$tmp.unsorted" > "$tmp"
mv "$out/details.tsv.new" "$out/details.tsv" 2>/dev/null

total=$(grep -c '' "$tmp")
commit=$(git rev-parse --short HEAD 2>/dev/null)
echo "# Module smoke test"
echo
echo "Every module of the install ($total), started headless straight into the module with a default party (the player, Carth and Bastila, the test bot in god mode touring the area and fighting what is hostile in sight) and left running for $((frames / 30)) s of world time. Run by \`kotor/tools/smoke/run.sh\` ($(date +%F), commit $commit); \`--no-render --speed 8 --mute\`, one process per core. Read the table as a list of things to look at: the engine has nothing to say about a module that is clean."
echo
awk -F "$tab" '
  { n++; if ($2 != "ok") bad++; vm += $4; sc += $5; le += $6; mc += $7; mr += $16; st += $8; tx += $9; w += $11; if ($10 > worst) { worst = $10; wm = $1 } }
  END {
    printf "- **%d** modules run, **%d** crashed or timed out, **%d** VM faults and **%d** script faults, **%d** load errors, **%d** distinct routines missing (**%d** calls, summed over modules), **%d** stuck actions, **%d** missing textures.\n", n, bad, vm, sc, le, mr, mc, st, tx
    printf "- Wall time summed over the runs: %d s; the slowest loop was %s ms per tick on average (%s).\n", w, worst, wm
  }' "$tmp"
echo
echo "Columns: **VM** faults are the VM's own invariants broken (stack underflow or overflow, bad offsets, unbalanced scripts, STORE_STATE misuse, an engine reply of the wrong kind); **script** faults are what a script (or a routine given bad arguments) did: a runaway loop, a wrong type, a routine that failed, a division by zero. **Missing** counts the routines called that no category implements (names and calls). **Stuck** is an action of a kind that should end soon (a walk, a door, a pick-up) that had run over 20 s and stood in the same place 10 s of world time later. **Load** counts error lines (\`kotor:\`, \`visual\`, panels); **Tex** the textures not found. **Tour** is the bot's stops reached of the stops it picked (waypoints, doors, placeables, triggers, talkers); **World s** the world time that passed (less than the run's length means the clock stopped: a screen or a pause held it). **ms** is the average and slowest wall time of a loop pass, with the world's ticks inside it."
echo
echo "| Module | Status | VM | Script | Missing | Stuck | Load | Tex | Tour | Went on to | World s | ms avg | ms max | Wall s |"
echo "|---|---|--:|--:|---|--:|--:|--:|--:|---|--:|--:|--:|--:|"
awk -F "$tab" '{
  miss = ($16 > 0) ? $16 " (" $7 " calls): " $13 : "-"
  stuck = ($8 > 0) ? $8 " (" $14 ")" : "-"
  st = ($2 == "ok") ? "ok" : "**" $2 "**"
  printf "| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %.2f | %.0f | %s |\n", $1, st, ($4 > 0 ? $4 : "-"), ($5 > 0 ? $5 : "-"), miss, stuck, ($6 > 0 ? $6 : "-"), ($9 > 0 ? $9 : "-"), $18, $19, $17, $10, $12, $11
}' "$tmp"

# The details: the faults by script and kind, the load errors, the crashes.
if [ -s "$out/details.tsv" ]; then
  echo
  echo "## Faults and load errors"
  echo
  echo "| Module | Script / error | Kind | Count |"
  echo "|---|---|---|--:|"
  grep '^D' "$out/details.tsv" | awk -F "$tab" '{ printf "| %s | %s | %s | %s |\n", $2, substr($3, 1, index($3, " | ") - 1), substr($3, index($3, " | ") + 3), $4 }' | sort
  grep '^L' "$out/details.tsv" | awk -F "$tab" '{ printf "| %s | load | %s | 1 |\n", $2, $3 }' | sort
fi
if awk -F "$tab" '$2 != "ok" { f = 1 } END { exit !f }' "$tmp"; then
  echo
  echo "## Crashes and timeouts"
  echo
  awk -F "$tab" '$2 != "ok" { printf "- `%s`: %s %s\n", $1, $2, $15 }' "$tmp"
fi
echo
echo "## Slowest modules"
echo
echo "| Module | ms per loop pass | slowest pass ms | wall s |"
echo "|---|--:|--:|--:|"
sort -t "$tab" -k10,10nr "$tmp" | head -8 | awk -F "$tab" '{ printf "| %s | %.2f | %.0f | %s |\n", $1, $10, $12, $11 }'
rm -f "$tmp" "$tmp.unsorted"
