"""Generate another_game_framework's KOTOR quests from the install.

    python kotor/tools/py/agf_quests.py [--agf DIR]

Writes `apps/kotor/src/quests.ts` in the framework repo (default G:/Dev/another_game_framework):
every quest (category) of `global.jrl` with its name and priority, and each of its entries (journal.md)
as a quest entry: its state (`ID`), text and whether it ends the quest (`End`). A quest's id is its
tag lower-cased, as the game matches tags without case; an entry's id adds `:<state>`. Entries keep
the file's order.

Left out for now, and counted: the quest's planet (`PlanetID`) and the experience a step pays
(`PlotIndex`, `XP_Percentage`).
"""
import argparse
import json
import os
import sys

import gffpy
import kres
import tlkpy
from agf_containers import DEFAULT_AGF


def text_of(tlk, loc):
    if loc.strref != 0xFFFFFFFF and loc.strref < len(tlk):
        return tlk.text(loc.strref) or ''
    if loc.strings:
        return next(iter(loc.strings.values()))
    return ''


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--agf', default=DEFAULT_AGF, help='the framework repo')
    args = ap.parse_args(argv)

    game = kres.Game()
    tlk = tlkpy.load(game.dir)
    key = {(e.resref, e.ext): e for e in kres.read_key(game.dir)}
    root = gffpy.read(kres.read_entry(key[('global', 'jrl')]))

    q = lambda s: json.dumps(s, ensure_ascii=False)  # noqa: E731
    quests, entries, seen = [], [], set()
    with_planet = with_xp = 0
    for cat in root['Categories']:
        quest_id = cat['Tag'].lower()
        if quest_id in seen:
            raise SystemExit(f'{cat["Tag"]} is in global.jrl twice')
        seen.add(quest_id)
        quests.append(f'  {{ id: {q(quest_id)}, name: {q(text_of(tlk, cat["Name"]))},'
                      f' priority: {cat["Priority"]} }},')
        with_planet += cat['PlanetID'] != -1
        states = set()
        for e in cat['EntryList']:
            state = e['ID']
            if state in states:
                raise SystemExit(f'{cat["Tag"]} has entry {state} twice')
            states.add(state)
            with_xp += cat['PlotIndex'] != -1 and e['XP_Percentage'] > 0
            ends = 'true' if e['End'] else 'false'
            entries.append(f'  {{ id: {q(f"{quest_id}:{state}")}, questId: {q(quest_id)},'
                           f' state: {state}, text: {q(text_of(tlk, e["Text"]))}, ends: {ends} }},')

    out = ['import type { Quest, QuestEntry } from "@agf/core";', '',
           '/**',
           " * KOTOR's quests, from its journal (`global.jrl`): ids are the tags lower-cased, as KOTOR",
           ' * matches them without case.',
           ' *',
           " * Generated from the install by the RE repo's `kotor/tools/py/agf_quests.py`.",
           ' */',
           'export const KOTOR_QUESTS: Quest[] = [', *quests, '];', '',
           '/**',
           " * Each quest's entries, in the journal's order: an id adds the entry's state to its quest's.",
           ' *',
           " * Generated from the install by the RE repo's `kotor/tools/py/agf_quests.py`.",
           ' */',
           'export const KOTOR_QUEST_ENTRIES: QuestEntry[] = [', *entries, '];', '']
    path = os.path.join(args.agf, 'apps', 'kotor', 'src', 'quests.ts')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(out))

    print(f'wrote {path}: {len(quests)} quests, {len(entries)} entries')
    print(f'left out: the planet of {with_planet} quests, the experience of {with_xp} entries')


if __name__ == '__main__':
    main(sys.argv[1:])
