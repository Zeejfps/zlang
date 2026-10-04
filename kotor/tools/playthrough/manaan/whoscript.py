"""Which resources of the Manaan modules name a script (an event slot, a conversation node): dev tooling.

    python kotor/tools/playthrough/manaan/whoscript.py SCRIPT...

Reads every resource of the module containers (manm26aa.rim ... manm28ad_s.rim) and looks for the name in the bytes of the
GFF types that can carry a script (are, git, utc, utd, utp, utt, ute, uts, utw, dlg, ifo). A name that is a prefix of
another script's (k_pman_jail0 / k_pman_jail01) matches both; read the line it prints."""
import glob
import os
import sys

sys.path.insert(0, 'kotor/tools/py')
import kres

game_dir = os.environ.get('KOTOR_DIR', kres.DEFAULT_DIR)
KINDS = {'are', 'git', 'utc', 'utd', 'utp', 'utt', 'ute', 'uts', 'utw', 'dlg', 'ifo', 'utm'}
names = [n.lower().encode() for n in sys.argv[1:]]
for path in sorted(glob.glob(os.path.join(game_dir, 'modules', 'man*.rim'))):
    for e in kres.read_container(path):
        if e.ext not in KINDS:
            continue
        data = kres.read_entry(e).lower()
        for n in names:
            if n in data:
                print(f'{n.decode()}: {os.path.basename(path)} {e.resref}.{e.ext}')
