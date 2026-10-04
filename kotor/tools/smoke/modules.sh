#!/bin/sh
# The modules of the install, one name a line: every modules/NAME.rim and NAME.mod, not the NAME_s.rim
# next to it that holds the module's scripts and stream.  sh kotor/tools/smoke/modules.sh [GAME_DIR]
game=${1:-${GAME:-/f/Steam/steamapps/common/swkotor}}
ls "$game/modules" | grep -i -E '\.(rim|mod)$' | grep -v -i -E '_s\.rim$' | sed -E 's/\.[A-Za-z]+$//' | sort -f -u
