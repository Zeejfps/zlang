#!/bin/sh
# The status summary (docs/re/gui.md "CSWGuiStatusSummary"): plays the Endar Spire's security terminal
# (kotor/tools/items/scripts/status_summary.txt: overload the power conduit, 120 XP and spikes used up) twice,
# headless, and fails with a FAIL line each and exit 1 when
#   - with the option on, the panel did not open after the conversation with the XP and the lost items
#     (`status summary: flags 9 credits 0 xp 120`), or its OK could not be clicked at frame 800;
#   - with the option off (`ui summary off`), anything but the HUD's icons came of it
#     (`status summary icons: flags 9 ...`, no panel).
#
#   sh kotor/tools/camcheck/summary.sh          (from the repository root; EXE=PATH for another executable; ~20 s)
#
# Pictures: kotor/out/items/sum_panel.png (the panel), sum_after.png (after OK: the XP and item-lost icons by the
# minimap), sumoff_icons.png (option off: the icons only).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
export EXE=${EXE:-kotor/out/kotor.exe}
export LOG=dialog,scripts
script=kotor/tools/items/scripts/status_summary.txt
mkdir -p kotor/out/items
sed 's/^61 ui summary panel$/61 ui summary panel\n61 ui summary off/' $script > kotor/out/items/status_summary_off.txt
sh kotor/tools/items/run.sh sum module:end_m01ab $script 900 770:panel 830:after > /dev/null
sh kotor/tools/items/run.sh sumoff module:end_m01ab kotor/out/items/status_summary_off.txt 900 770:icons > /dev/null
fail=0
if grep -a -q 'status summary: flags 9 credits 0 xp 120 ' kotor/out/items/sum.raw; then echo "ok   panel: XP 120 and items lost"; else echo "FAIL option on: no 'status summary: flags 9 credits 0 xp 120' (panel) in kotor/out/items/sum.raw"; fail=1; fi
if grep -a -q '^ctl: no shown control BTN_OK' kotor/out/items/sum.raw; then echo "FAIL option on: no panel with BTN_OK to click at frame 800"; fail=1; else echo "ok   OK clicked"; fi
if grep -a -q 'status summary icons: flags 9 credits 0 xp 120 ' kotor/out/items/sumoff.raw && ! grep -a -q 'status summary: ' kotor/out/items/sumoff.raw; then echo "ok   option off: icons only"; else echo "FAIL option off: want 'status summary icons: flags 9 ...' and no panel in kotor/out/items/sumoff.raw"; fail=1; fi
exit $fail
