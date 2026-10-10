"""Generate another_game_framework's KOTOR global variables from the install.

    python kotor/tools/py/agf_globals.py [--agf DIR]

Writes `apps/kotor/src/scriptVariables.ts` in the framework repo (default
G:/Dev/another_game_framework): every boolean and number in `globalcat.2da`, the catalogue of the
global variables scripts set and read (party-items-saves.md 2.1), as the framework's script variables. An id is the name lower-cased, as
the game looks names up without case. The location and string globals are left out and listed.
"""
import argparse
import json
import os
import sys

import kres
import twodapy
from agf_containers import DEFAULT_AGF

KINDS = ('boolean', 'number')


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--agf', default=DEFAULT_AGF, help='the framework repo')
    args = ap.parse_args(argv)

    catalogue = twodapy.parse(kres.Game().get('globalcat', '2da'))
    rows, left_out, seen = [], [], set()
    for name, kind in zip(catalogue.column('name'), catalogue.column('type')):
        global_id = name.lower()
        if global_id in seen:
            raise SystemExit(f'{name} is in the catalogue twice')
        seen.add(global_id)
        if kind.lower() not in KINDS:
            left_out.append((name, kind))
            continue
        rows.append((global_id, kind.lower()))

    q = lambda s: json.dumps(s, ensure_ascii=False)  # noqa: E731
    out = ['import type { ScriptVariable } from "@agf/core";', '',
           '/**',
           " * KOTOR's global variables, from its catalogue (`globalcat.2da`): the flags and numbers",
           ' * scripts set and read. Ids are the names lower-cased, as KOTOR looks them up without case.',
           ' *',
           " * Generated from the install by the RE repo's `kotor/tools/py/agf_globals.py`.",
           ' */',
           'export const KOTOR_SCRIPT_VARIABLES: ScriptVariable[] = [']
    for global_id, kind in rows:
        out.append(f'  {{ id: {q(global_id)}, kind: {q(kind)} }},')
    out += ['];', '']
    path = os.path.join(args.agf, 'apps', 'kotor', 'src', 'scriptVariables.ts')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(out))

    print(f'wrote {path}: {len(rows)} globals'
          f' ({sum(k == "boolean" for _, k in rows)} booleans,'
          f' {sum(k == "number" for _, k in rows)} numbers)')
    print(f'left out: {len(left_out)}')
    for name, kind in left_out:
        print(f'    {name} ({kind})')


if __name__ == '__main__':
    main(sys.argv[1:])
