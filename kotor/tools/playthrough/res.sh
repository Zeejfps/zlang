#!/bin/sh
# Lists the install's resources whose name contains a word: sh kotor/tools/playthrough/res.sh WORD [resls options]
# (build kotor/tools/resls to kotor/out/resls.exe first)
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
word=$1
shift
kotor/out/resls.exe "$@" "*${word}*"
