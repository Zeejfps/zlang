#!/bin/sh
# Scripted character creations, with a picture of every screen under kotor/out/chargen/ and a check
# of each finished player against the tables. Run from the repository root after building:
#
#   kotor/tools/ctxc exe kotor/tools/chargentest -o kotor/out/chargentest.exe
#   sh kotor/tools/chargentest/selftest.sh
#
# Exit status 0 when every creation reached Play and every check held.
EXE=${EXE:-kotor/out/chargentest.exe}
OUT=kotor/out/chargen
PLAYER=$OUT/player.utc
mkdir -p $OUT
bad=0

run() {
    name=$1
    shift
    echo "== $name"
    rm -f $PLAYER
    if "$EXE" --out $OUT "$@" > $OUT/last.log 2>&1; then :; else bad=$((bad + 1)); echo "   run failed"; fi
    grep -E "FAIL|verify:|outcome:" $OUT/last.log | sed 's/^/   /'
    if [ ! -f $PLAYER ]; then bad=$((bad + 1)); echo "   no player was made"; fi
}

# Quick character, every screen photographed (a male Soldier, the third button).
run "quick soldier" click:BTN_NEWGAME wait:20 shot:q_class click:BTN_SEL3 wait:10 shot:q_choice \
    click:QUICK_CHAR_BTN wait:10 shot:q_steps click:BTN_STEPNAME1 wait:10 shot:q_portrait click:BTN_ARRR*2 wait:5 shot:q_portrait2 \
    click:BTN_ACCEPT wait:5 shot:q_summary click:BTN_STEPNAME2 shot:q_name click:END_BTN shot:q_ready click:BTN_STEPNAME3 \
    verifyquick:$PLAYER

# Custom character: the soldier's recommended scores bought by hand, the rest recommended.
run "custom soldier" click:BTN_NEWGAME click:BTN_SEL3 click:CUST_CHAR_BTN wait:5 shot:c_steps \
    click:BTN_STEPNAME1 click:BTN_ARRL*2 click:BTN_ACCEPT click:BTN_STEPNAME2 \
    click:STR_PLUS_BTN*8 click:DEX_PLUS_BTN*6 click:CON_PLUS_BTN*6 click:WIS_PLUS_BTN*4 click:INT_PLUS_BTN*2 shot:c_attributes \
    click:BTN_ACCEPT shot:c_attributes_left click:BTN_OK click:CHA_PLUS_BTN*2 click:BTN_ACCEPT shot:c_summary \
    click:BTN_STEPNAME3 click:TRE_PLUS_BTN*4 shot:c_skills click:BTN_ACCEPT click:BTN_STEPNAME4 shot:c_feats click:BTN_RECOMMENDED shot:c_feats_picked \
    click:BTN_ACCEPT click:BTN_STEPNAME5 shot:c_name click:END_BTN shot:c_ready click:BTN_STEPNAME6 verify:$PLAYER

# Every class and gender, quick; and the other two classes, custom with the recommended buttons.
for slot in 1 2 4 5 6; do
    run "quick slot $slot" click:BTN_NEWGAME click:BTN_SEL$slot click:QUICK_CHAR_BTN click:BTN_STEPNAME1 click:BTN_ARRR click:BTN_ACCEPT \
        click:BTN_STEPNAME2 click:END_BTN click:BTN_STEPNAME3 verifyquick:$PLAYER
done
for slot in 1 2; do
    run "custom slot $slot" click:BTN_NEWGAME click:BTN_SEL$slot click:CUST_CHAR_BTN click:BTN_STEPNAME1 click:BTN_ACCEPT \
        click:BTN_STEPNAME2 click:BTN_RECOMMENDED click:BTN_ACCEPT click:BTN_STEPNAME3 click:BTN_RECOMMENDED click:BTN_ACCEPT \
        click:BTN_STEPNAME4 click:BTN_RECOMMENDED click:BTN_ACCEPT click:BTN_STEPNAME5 click:END_BTN click:BTN_STEPNAME6 verify:$PLAYER
done

# Backing out: Cancel on the quick-or-custom list returns to class selection; Cancel after a step asks first.
run "back out" click:BTN_NEWGAME click:BTN_SEL2 click:BTN_BACK wait:5 shot:b_class click:BTN_SEL4 click:CUST_CHAR_BTN \
    click:BTN_STEPNAME1 click:BTN_ACCEPT click:BTN_CANCEL shot:b_confirm key:e click:BTN_SEL5 click:QUICK_CHAR_BTN \
    click:BTN_STEPNAME1 click:BTN_ACCEPT click:BTN_STEPNAME2 click:END_BTN click:BTN_STEPNAME3 verifyquick:$PLAYER

if [ $bad -ne 0 ]; then echo "selftest: $bad problems"; exit 1; fi
echo "selftest: all creations made and checked"
