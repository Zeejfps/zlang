#!/bin/sh
# A computer terminal's camera view and its XP: plays the Endar Spire's security terminal (end_comp02 in
# end_m01ab, kotor/tools/items/scripts/computer_camera.txt: view the starboard transport module, then overload
# the power conduit) headless and fails, with a FAIL line each and exit 1, when
#   - the camera view does not show the 3D picture: the computer panel is centred with black on both sides, so
#     the left eighth of the screen must be lit, and blue-grey under the security camera's video effect
#     (videoeffects.2da row 0: saturation 0.15, modulation 1, 1.4, 2);
#   - the log has no `dialog video effect 0` for each of the three camera nodes;
#   - the plot XP of entry 7 (PlotIndex 47 x 0.1 = 100) is not paid with its feedback line.
#
#   sh kotor/tools/camcheck/computer.sh          (from the repository root; EXE=PATH for another executable; ~10 s)
#
# The picture is kotor/out/items/cc_view.png, the log kotor/out/items/cc.raw (docs/testing.md, "Conversation shots").
py=$(command -v python)    # before the PATH change below: the MSYS2 python has no numpy
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
export EXE=${EXE:-kotor/out/kotor.exe}
export LOG=dialog
rm -f kotor/out/items/cc_view.png
sh kotor/tools/items/run.sh cc module:end_m01ab kotor/tools/items/scripts/computer_camera.txt 760 150:view > /dev/null
fail=0
effects=$(grep -a -c 'dialog video effect 0 ' kotor/out/items/cc.raw)
# The Carth call at the start of the module is a fourth (end_carth001, CamVidEffect 0).
if [ "$effects" -lt 4 ]; then echo "FAIL video effect switched on $effects times, want 4"; fail=1; else echo "ok   video effect on $effects times"; fi
if grep -a -q '^log: Experience Points (XP) Received: 100$' kotor/out/items/cc.raw; then echo "ok   plot XP 100 with its feedback"; else echo "FAIL no 'Experience Points (XP) Received: 100' in the message log"; fail=1; fi
"$py" - kotor/out/items/cc_view.png <<'EOF' || fail=1
import sys
import numpy as np
from PIL import Image
path = sys.argv[1]
try:
    a = np.asarray(Image.open(path).convert('RGB')).astype(np.float32)
except OSError:
    print(f'FAIL {path}: no picture')
    sys.exit(1)
h, w, _ = a.shape
strip = a[int(h * 0.18):int(h * 0.82), int(w * 0.01):int(w * 0.125)]
lum = (0.299 * strip[..., 0] + 0.587 * strip[..., 1] + 0.114 * strip[..., 2]).mean()
r, b = strip[..., 0].mean(), strip[..., 2].mean()
ok = lum >= 10 and b >= r * 1.2
print(f'{"ok  " if ok else "FAIL"} camera view left strip: mean {lum:.1f}, blue/red {b / max(r, 1):.2f} (want 10+ and 1.2+)')
sys.exit(0 if ok else 1)
EOF
exit $fail
