#!/bin/sh
# The sweep's tables, as markdown on standard output, from a run's logs.   sh report.sh OUTDIR
# (OUTDIR holds modules/MODULE.log and pairs/MODULE__DLG.log from one.sh.)
out=${1:-kotor/out/dlgsweep}
tab=$(printf '\t')
tsv=$out/convs.tsv
faults=$out/faults.tsv
fails=$out/fails.tsv

# One line a dialogue (a fresh process each): END lines, and the engine's fault lines between BEGIN and END.
awk -v tab="$tab" -v faults="$faults" -v fails="$fails" '
  FNR == 1 { inside = 0; nd = 0; delete det }
  /^BEGIN / { inside = 1; nd = 0; delete det }
  inside && /fault: / {
    line = $0; sub(/^.*fault: /, "", line)
    script = line; sub(/ .*/, "", script)
    rest = line; sub(/^[^:]*: /, "", rest); kind = rest; sub(/:.*/, "", kind)
    det[script ": " kind]++
  }
  /^LOADFAIL / { printf "%s\t%s\t%s\n", $2, FILENAME, substr($0, length($1) + length($2) + 3) > fails; inside = 0 }
  /^END / {
    inside = 0
    name = $2; module = $3
    owner = $4; sub(/^owner=/, "", owner); how = owner; sub(/.*\(/, "", how); sub(/\).*/, "", how); sub(/\(.*/, "", owner)
    for (i = 5; i <= NF; i++) { split($i, kv, "="); v[kv[1]] = substr($i, length(kv[1]) + 2) }
    split(v["reached"], rr, "/")
    fd = ""
    for (k in det) { fd = fd (fd != "" ? "; " : "") k " x" det[k]; print name tab module tab k tab det[k] > faults }
    sp = v["speakers_missing"]; spn = sp; sub(/:.*/, "", spn); spt = sp; sub(/^[0-9]*:/, "", spt)
    printf "%s\t%s\t%s\t%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s\t%s\t%d\t%s\t%d\t%s\n", name, module, owner, how, v["entries"], v["replies"], rr[1], rr[2], v["scripts"], v["true"], v["false"], v["faults"], v["missing_scripts"], v["missing_routines"], spn, spt, v["link_errors"], fd
    delete v
  }' "$out"/pairs/*.log > "$tsv"
: > "$faults.x"
[ -f "$faults" ] || : > "$faults"
[ -f "$fails" ] || : > "$fails"

n=$(grep -c '' "$tsv")
commit=$(git rev-parse --short HEAD 2>/dev/null)
bad_rc=$(cat "$out"/pairs/*.rc "$out"/modules/*.rc 2>/dev/null | grep -c -v '^0$')

echo "# Conversation sweep"
echo
echo "Every dialogue of the install ($n of them, a module's own copy of a name counting once per module that names it), walked node by node by \`kotor/tools/dlgsweep/run.sh\` ($(date +%F), commit $commit). Each runs in a freshly entered module (30 frames of the world first) with the object that names it as the owner, a stand-in creature when none does, and the player as the other side. From the starting list the walk visits every entry and reply reachable by links; at each link it runs the Active script and counts the answer but goes on through the link whatever it was (**forced true**); at each node it runs the action script; at the end the abort script, then the normal end (the end script and every creature's and placeable's end-of-dialogue script in the area), then 30 more frames for what the scripts delayed. Scripts run as in the game: with the owner as OBJECT_SELF, the PC speaker the player."
echo
awk -F "$tab" '
  { c++; ne += $5; nr += $6; re += $7; rr += $8; s += $9; t += $10; f += $11; fl += $12; how[$4]++
    if ($12 > 0) fc++
    if ($13 != "-") { ms++; n = split($13, a, ","); for (i = 1; i <= n; i++) mscript[a[i]] = 1 }
    if ($14 != "-") mr++
    if ($15 > 0) { sp++; if ($4 == "object") spo++ }
    if ($7 < $5 || $8 < $6) un++
    if ($17 > 0) le++
  }
  END {
    nm = 0; for (k in mscript) nm++
    printf "- **%d** dialogues swept: **%d** with the object that names them as owner, **%d** with a stand-in creature, **%d** with the player (no creature in the module).\n", c, how["object"], how["standin"], how["player"]
    printf "- **%d** entries and **%d** replies; **%d** entries and **%d** replies reached; **%d** dialogues with a node no link leads to.\n", ne, nr, re, rr, un + 0
    printf "- **%d** scripts run, **%d** Active scripts answered true and **%d** false (every link was taken regardless).\n", s, t, f
    printf "- **%d** script faults in **%d** dialogues; **%d** dialogues called routines nothing implements; **%d** dialogues name **%d** distinct scripts the install does not have; **%d** have an entry whose speaker is not in the module (%d with a real owner); **%d** have a link past the end of its list.\n", fl, fc, mr, ms, nm, sp, spo + 0, le + 0
  }' "$tsv"
echo "- Dialogues that failed to load: **$(grep -c '' "$fails")**; processes that crashed or timed out: **$bad_rc**."
echo
echo "A dialogue gets a row in the sections below only for something to look at. Faults in a dialogue's scripts are listed with the script that faulted and what the VM said; a fault in a script the dialogue does not name (\`k_def_endconv\`, \`k_ai_master\`) came from the area's end-of-dialogue handlers or the world frames after it."

echo
echo "## Script faults"
echo
if [ -s "$faults" ]; then
  echo "| Dialogue | Module | Owner | Faults | Script: what happened |"
  echo "|---|---|---|--:|---|"
  awk -F "$tab" '$12 > 0 { printf "%d\t%s\t%s\t%s\t%s\n", $12, $1, $2, $3, $18 }' "$tsv" | sort -t "$tab" -k1,1nr -k2,2 | awk -F "$tab" '{ printf "| %s | %s | %s | %s | %s |\n", $2, $3, $4, $1, $5 }'
  echo
  echo "By script and kind:"
  echo
  echo "| Script | What happened | Faults | Dialogues |"
  echo "|---|---|--:|--:|"
  awk -F "$tab" '{ split($3, a, ": "); key = $3; n[key] += $4; d[key]++ } END { for (k in n) printf "%d\t%s\t%d\n", n[k], k, d[k] }' "$faults" | sort -t "$tab" -k1,1nr | awk -F "$tab" '{ i = index($2, ": "); printf "| `%s` | %s | %d | %d |\n", substr($2, 1, i - 1), substr($2, i + 2), $1, $3 }'
else
  echo "None."
fi

echo
echo "## Routines called that nothing implements"
echo
if awk -F "$tab" '$14 != "-" { f = 1 } END { exit !f }' "$tsv"; then
  echo "| Dialogue | Module | Routines (calls) |"
  echo "|---|---|---|"
  awk -F "$tab" '$14 != "-" { printf "| %s | %s | %s |\n", $1, $2, $14 }' "$tsv"
else
  echo "None: every routine the dialogues' scripts called is implemented."
fi

echo
echo "## Dialogues that failed to load"
echo
if [ -s "$fails" ]; then
  echo "| Dialogue | Process | Error |"
  echo "|---|---|---|"
  awk -F "$tab" '{ f = $2; sub(/.*\//, "", f); sub(/\.log$/, "", f); printf "| %s | %s | %s |\n", $1, f, $3 }' "$fails"
else
  echo "None."
fi

echo
echo "## Scripts the dialogues name that the install does not have"
echo
echo "The engine treats a missing Active script as false and a missing action script as nothing, as the game does; the list is the data's own."
echo
if awk -F "$tab" '$13 != "-" { f = 1 } END { exit !f }' "$tsv"; then
  echo "| Script | Dialogues |"
  echo "|---|---|"
  awk -F "$tab" '$13 != "-" { n = split($13, a, ","); for (i = 1; i <= n; i++) { if (!(a[i] in seen) || index(seen[a[i]], $1) == 0) { seen[a[i]] = seen[a[i]] (seen[a[i]] != "" ? ", " : "") $1 } } } END { for (k in seen) printf "| `%s` | %s |\n", k, seen[k] }' "$tsv" | sort
else
  echo "None."
fi

echo
echo "## Speakers that are not in the module"
echo
echo "An entry whose Speaker tag is neither the owner nor an object in the owner's area is skipped by the flow (the conversation ends if it was the one to play). Many are spawned or placed by earlier scripts or are in another module's copy, so this is a list to read, not a list of bugs. Dialogues swept with a stand-in owner are left out (the tags are meant for their own owner's module)."
echo
if awk -F "$tab" '$15 > 0 && $4 == "object" { f = 1 } END { exit !f }' "$tsv"; then
  echo "| Dialogue | Module | Entries | Tags (first three) |"
  echo "|---|---|--:|---|"
  awk -F "$tab" '$15 > 0 && $4 == "object" { printf "| %s | %s | %d | %s |\n", $1, $2, $15, $16 }' "$tsv" | sort
else
  echo "None."
fi

echo
echo "## Processes that crashed or timed out"
echo
if [ "$bad_rc" != "0" ]; then
  for f in "$out"/pairs/*.rc "$out"/modules/*.rc; do
    [ "$(cat "$f")" = "0" ] || echo "- \`$(basename "$f" .rc)\`: exit $(cat "$f")"
  done
else
  echo "None."
fi
rm -f "$faults.x"
