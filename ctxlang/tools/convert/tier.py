"""Moves each case the runner failed to its next tier (convert.py), from the runner's output.

    python tools/convert/tier.py RUNNER_OUTPUT TIERS.json
"""
import json, os, re, sys
out, path = sys.argv[1], sys.argv[2]
tiers = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
failed = set()
for line in open(out, encoding='utf-8', errors='replace'):
    m = re.match(r'^.*?:\d+: fail: ([^:]+): ', line)
    if m:
        failed.add(m.group(1))
moved = 0
for name in sorted(failed):
    if tiers.get(name, 1) < 3:
        tiers[name] = tiers.get(name, 1) + 1
        moved += 1
json.dump(tiers, open(path, 'w', encoding='utf-8'), indent=0, sort_keys=True)
print(f'{len(failed)} failed, {moved} moved to the next tier')
