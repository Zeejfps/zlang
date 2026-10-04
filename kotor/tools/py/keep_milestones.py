"""Copies the numbered manual saves of kotor/out/saves ("000002 - Game1", ... in the order they were made) to
kotor/out/ms/NAME, naming them by their save name (savenfo.res holds "ms_NAME" in SAVEGAMENAME) - so a
check can `load kotor/out/ms/NAME`. Used by kotor/tools/playthrough/milestones.sh."""
import os, re, shutil, sys

saves = 'kotor/out/saves'
out = 'kotor/out/ms'
os.makedirs(out, exist_ok=True)
for d in sorted(os.listdir(saves)):
    if not re.match(r'^\d{6} - Game\d+$', d):
        continue
    nfo = open(os.path.join(saves, d, 'savenfo.res'), 'rb').read()
    m = re.search(rb'ms_([A-Za-z0-9]+)', nfo)
    if not m:
        continue
    name = m.group(1).decode()
    shutil.rmtree(os.path.join(out, name), ignore_errors=True)
    shutil.copytree(os.path.join(saves, d), os.path.join(out, name))
    print('%-12s <- %s' % (name, d))
