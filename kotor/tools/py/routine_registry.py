#!/usr/bin/env python3
"""Which NWScript routines does the engine implement, and in which file? (dev tooling)

Reads every kotor/lib/engine/routines/*.ctx, collects the routine names its dispatch claims
(`routine == nwscript::NAME` anywhere in the file, and `nwscript::NAME =>` / `nwscript::A | nwscript::B =>`
/ `nwscript::A..=nwscript::B =>` arms of an integer `match routine`), turns names into ids with
lib/script/routines.ctx's constants, joins them with docs/formats/nwscript-routines.tsv (the
usage ranking by number of shipped scripts), and writes docs/design/routines.tsv:

    id  name  file  ncs_files          (sorted by id; file is the category file, e.g. core.ctx)

It prints how many of the 772 routines are implemented, how many of the top 150 by ncs_files,
the busiest ones still missing, and exits 1 if one id is claimed by two files (or a claimed name
is not a routine), 0 otherwise.

    python kotor/tools/py/routine_registry.py [--missing N]
"""
import argparse
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KOTOR = os.path.normpath(os.path.join(HERE, "..", ".."))
ROUTINE_DIR = os.path.join(KOTOR, "lib", "engine", "routines")
CONSTANTS = os.path.join(KOTOR, "lib", "script", "routines.ctx")
USAGE = os.path.join(KOTOR, "docs", "formats", "nwscript-routines.tsv")
OUT = os.path.join(KOTOR, "docs", "design", "routines.tsv")

NAME = r"nwscript::(\w+)"


def load_ids():
    """name -> id from the `const NAME: u16 = N` lines of lib/script/routines.ctx."""
    ids = {}
    pat = re.compile(r"^\s*const\s+(\w+)\s*:\s*u16\s*=\s*(\d+)\b")
    with open(CONSTANTS, encoding="utf-8") as f:
        for line in f:
            m = pat.match(line)
            if m and m.group(1) != "COUNT":
                ids[m.group(1)] = int(m.group(2))
    return ids


def load_usage():
    """id -> (name, ncs_files) from the usage ranking."""
    usage = {}
    with open(USAGE, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            usage[int(row["index"])] = (row["name"], int(row["ncs_files"]))
    return usage


def claims(path):
    """The routine names a category file dispatches on, in order of first appearance."""
    found = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.split("//", 1)[0]
            for m in re.finditer(r"\broutine\s*==\s*" + NAME, line):
                found.append(m.group(1))
            stripped = line.strip()
            if "=>" in stripped:
                head = stripped.split("=>", 1)[0]
            elif stripped.endswith("|"):
                head = stripped
            else:
                continue
            if not head.startswith("nwscript::"):
                continue
            # A range arm `nwscript::A..=nwscript::B` claims every id between the two.
            for m in re.finditer(NAME + r"\s*\.\.=\s*" + NAME, head):
                found.append(("range", m.group(1), m.group(2)))
            head = re.sub(NAME + r"\s*\.\.=\s*" + NAME, "", head)
            for m in re.finditer(NAME, head):
                found.append(m.group(1))
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--missing", type=int, default=12, help="how many of the busiest missing routines to list")
    args = ap.parse_args()

    ids = load_ids()
    by_id = {v: k for k, v in ids.items()}
    usage = load_usage()
    problems = []

    owner = {}  # id -> file
    for fname in sorted(os.listdir(ROUTINE_DIR)):
        if not fname.endswith(".ctx") or fname == "dispatch.ctx":
            continue
        for item in claims(os.path.join(ROUTINE_DIR, fname)):
            if isinstance(item, tuple):
                _, lo, hi = item
                if lo not in ids or hi not in ids:
                    problems.append("%s: range %s..=%s names no routine" % (fname, lo, hi))
                    continue
                span = range(ids[lo], ids[hi] + 1)
            else:
                if item not in ids:
                    problems.append("%s: nwscript::%s is not a routine" % (fname, item))
                    continue
                span = [ids[item]]
            for i in span:
                if i in owner and owner[i] != fname:
                    problems.append("routine %d %s claimed by %s and %s" % (i, by_id[i], owner[i], fname))
                else:
                    owner[i] = fname

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write("id\tname\tfile\tncs_files\n")
        for i in sorted(owner):
            f.write("%d\t%s\t%s\t%d\n" % (i, by_id[i], owner[i], usage.get(i, ("", 0))[1]))

    total = len(by_id)
    print("routines implemented: %d of %d (%s)" % (len(owner), total, os.path.relpath(OUT, KOTOR).replace("\\", "/")))
    per_file = {}
    for fname in owner.values():
        per_file[fname] = per_file.get(fname, 0) + 1
    print("  " + ", ".join("%s %d" % (k, per_file[k]) for k in sorted(per_file)))

    ranked = sorted(usage.items(), key=lambda kv: (-kv[1][1], kv[0]))
    top = ranked[:150]
    have = [i for i, _ in top if i in owner]
    print("top 150 by ncs_files: %d implemented, %d missing" % (len(have), len(top) - len(have)))
    for i, (name, n) in [kv for kv in top if kv[0] not in owner][: args.missing]:
        print("  missing %3d %-28s %4d files" % (i, name, n))
    used = [i for i, (_, n) in usage.items() if n > 0]
    print("routines used by any script: %d, implemented %d" % (len(used), len([i for i in used if i in owner])))

    for p in problems:
        print("ERROR: " + p, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
