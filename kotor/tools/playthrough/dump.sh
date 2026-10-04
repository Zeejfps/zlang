#!/bin/sh
# Prints a resource of a module as a GFF tree (build kotor/tools/gffdump to kotor/out/gffdump.exe):
#
#   sh kotor/tools/playthrough/dump.sh MODULE NAME EXT       e.g.  end_m01aa m01aa git
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
kotor/out/gffdump.exe --module "$1" "$2.$3"
