"""Generate another_game_framework's KOTOR dialogues from the install.

    python kotor/tools/py/agf_dialogues.py [--agf DIR]

Writes, under `apps/kotor/src/dialogues/` in the framework repo (default
G:/Dev/another_game_framework):

- `<planet>/<resref>.ts` for each conversation (DLG) in DIALOGUES, in the folder of the planet its
  module is on: the dialogue, its lines, starts and links. A line's id is the resref with `:E<n>`
  for an entry or `:R<n>` for a reply, its index in the DLG. Starts and links keep the DLG's order,
  and name their condition (`Active`) and each line its action (`Script`) by script resref. A line
  moving a quest on (`Quest`, `QuestEntry`) names the quest entry as `agf_quests.py` writes it;
  one naming state 0, which never moves a quest, names none, and one naming an entry
  `global.jrl` doesn't have stops the generator.
- `index.ts`: every dialogue's rows together, and the condition and action rows from the
  hand-written `scripts.ts`.
- `scriptIds.ts`: the union of every condition and action script the dialogues name, which the
  scripts must cover.
- `stubs.ts`: a stub for each script named that no hand-written `scripts.ts` under `dialogues/`
  ports: a condition that fails and an action that does nothing, which is what KOTOR does with a
  script it can't find. A script the game itself doesn't have gets the same stub, marked as
  missing rather than unported.

A script is looked up as the game does, in the dialogue's module, then the BIFs. Two dialogues
naming one resref that their modules hold different copies of stop the generator.
"""
import argparse
import hashlib
import json
import os
import re
import sys

import gffpy
import kres
import tlkpy
from agf_containers import DEFAULT_AGF, Install

DIALOGUES = ['tar02_zelka021']

# A module's first three letters -> the planet folder its dialogues go in.
PLANETS = {
    'end': 'endarSpire', 'tar': 'taris', 'ebo': 'ebonHawk', 'dan': 'dantooine',
    'kas': 'kashyyyk', 'man': 'manaan', 'tat': 'tatooine', 'kor': 'korriban', 'lev': 'leviathan',
    'unk': 'unknownWorld', 'sta': 'starForge', 'liv': 'yavinStation',
}

PORTED_BLOCK = re.compile(r'export const \w+_(CONDITIONS|ACTIONS) = \{(.*?)\n\}', re.S)
KEY = re.compile(r'^\s+"?([\w.]+)"?:', re.M)

HEADER = " * Generated from the install by the RE repo's `kotor/tools/py/agf_dialogues.py`."


def text_of(tlk, loc):
    if 0 <= loc.strref < min(len(tlk), 0xFFFFFFFF):
        return tlk.text(loc.strref) or ''
    if loc.strings:
        return next(iter(loc.strings.values()))
    return ''


def module_resources(install):
    """module -> (resref, ext) -> entry, a module's own resources (its RIM and _s RIM)."""
    out = {}
    for mod, files in install.modules().items():
        entries = {}
        for f in files:
            for e in kres.read_container(f):
                entries[(e.resref, e.ext)] = e
        out[mod] = entries
    return out


def find_dialogue(resources, resref):
    """The one module holding the DLG, and its data."""
    found = [(mod, entries[(resref, 'dlg')]) for mod, entries in sorted(resources.items())
             if (resref, 'dlg') in entries]
    if len(found) != 1:
        raise SystemExit(f'{resref}.dlg is in {len(found)} modules: add the module to DIALOGUES')
    mod, entry = found[0]
    return mod, gffpy.read(kres.read_entry(entry))


def quest_states(chitin):
    """quest tag, lower-cased -> the states of its entries in global.jrl."""
    root = gffpy.read(kres.read_entry(chitin[('global', 'jrl')]))
    return {c['Tag'].lower(): {e['ID'] for e in c['EntryList']} for c in root['Categories']}


def read_script(chitin, entries, resref):
    """The script's bytes as the module sees it, or None when the game has none."""
    entry = entries.get((resref, 'ncs')) or chitin.get(resref)
    return kres.read_entry(entry) if entry else None


def ported(folder):
    """'condition'/'action' -> the script resrefs every hand-written `scripts.ts` ports."""
    out = {'condition': set(), 'action': set()}
    for dirpath, _, files in os.walk(folder):
        if 'scripts.ts' not in files:
            continue
        src = open(os.path.join(dirpath, 'scripts.ts'), encoding='utf-8').read()
        for kind, body in PORTED_BLOCK.findall(src):
            out['condition' if kind == 'CONDITIONS' else 'action'] |= set(KEY.findall(body))
    return out


def write(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--agf', default=DEFAULT_AGF, help='the framework repo')
    args = ap.parse_args(argv)

    install = Install()
    keyed = kres.read_key(install.game.dir)
    chitin = {e.resref: e for e in keyed if e.ext == 'ncs'}
    quests = quest_states({(e.resref, e.ext): e for e in keyed})
    tlk = tlkpy.load()
    resources = module_resources(install)
    folder = os.path.join(args.agf, 'apps', 'kotor', 'src', 'dialogues')

    q = lambda s: json.dumps(s, ensure_ascii=False)  # noqa: E731
    key = lambda s: s if re.fullmatch(r'[A-Za-z_]\w*', s) else q(s)  # noqa: E731

    scripts = {'condition': {}, 'action': {}}  # resref -> (hash or None, dialogue)

    def use_script(kind, resref, mod, dlg):
        data = read_script(chitin, resources[mod], resref)
        digest = hashlib.sha1(data).hexdigest() if data else None
        seen = scripts[kind].get(resref)
        if seen and seen[0] != digest:
            raise SystemExit(f'{resref} differs between {seen[1]} and {dlg}')
        scripts[kind][resref] = (digest, dlg)

    written, totals = [], [0, 0, 0]  # (planet, resref); lines, starts, links
    for dlg in DIALOGUES:
        mod, root = find_dialogue(resources, dlg)
        planet = PLANETS[mod[:3]]
        nodes, links = [], []
        for kind, prefix, lst, child_list, child_prefix in (
                ('entry', 'E', 'EntryList', 'RepliesList', 'R'),
                ('reply', 'R', 'ReplyList', 'EntriesList', 'E')):
            for i, n in enumerate(root[lst]):
                node_id = f'{dlg}:{prefix}{i}'
                extra = ''
                quest, state = (n.get('Quest') or '').lower(), n.get('QuestEntry') or 0
                if quest and state != 0:
                    if state not in quests.get(quest, ()):
                        raise SystemExit(f'{node_id} names {quest} {state}, not in global.jrl')
                    extra += f', questEntryId: {q(f"{quest}:{state}")}'
                action = (n.get('Script') or '').lower()
                if action:
                    use_script('action', action, mod, dlg)
                    extra += f', actionId: {q(action)}'
                nodes.append(f'  {{ id: {q(node_id)}, dialogueId: {q(dlg)}, kind: {q(kind)},'
                             f' text: {q(text_of(tlk, n["Text"]))}{extra} }},')
                targets = set()
                for order, link in enumerate(n.get(child_list) or []):
                    target = f'{dlg}:{child_prefix}{link["Index"]}'
                    if target in targets:
                        raise SystemExit(f'{node_id} links to {target} twice')
                    targets.add(target)
                    condition = (link.get('Active') or '').lower()
                    if condition:
                        use_script('condition', condition, mod, dlg)
                    extra = f', conditionId: {q(condition)}' if condition else ''
                    links.append(f'  {{ fromNodeId: {q(node_id)}, toNodeId: {q(target)},'
                                 f' order: {order}{extra} }},')
        starts = []
        for order, link in enumerate(root['StartingList']):
            condition = (link.get('Active') or '').lower()
            if condition:
                use_script('condition', condition, mod, dlg)
            extra = f', conditionId: {q(condition)}' if condition else ''
            starts.append(f'  {{ dialogueId: {q(dlg)}, entryNodeId: {q(f"{dlg}:E{link['Index']}")},'
                          f' order: {order}{extra} }},')
        write(os.path.join(folder, planet, f'{dlg}.ts'), [
            'import type { Dialogue, DialogueLink, DialogueNode, DialogueStart } from "@agf/core";',
            '',
            '/**',
            f' * KOTOR\'s conversation `{dlg}` (module `{mod}`).',
            ' *',
            HEADER,
            ' */',
            f'export const DIALOGUE: Dialogue = {{ id: {q(dlg)} }};',
            '',
            'export const NODES: DialogueNode[] = [', *nodes, '];',
            '',
            'export const STARTS: DialogueStart[] = [', *starts, '];',
            '',
            'export const LINKS: DialogueLink[] = [', *links, '];',
            ''])
        written.append((planet, dlg))
        totals[0] += len(nodes)
        totals[1] += len(starts)
        totals[2] += len(links)

    index = ['import type { Dialogue, DialogueLink, DialogueNode, DialogueStart } from "@agf/core";']
    index += [f'import * as {dlg} from "./{planet}/{dlg}";' for planet, dlg in sorted(written)]
    index += ['',
              '/**',
              " * KOTOR's conversations (DLG), one file each in their planet's folder: ids are the",
              " * resrefs, and a line's id adds `:E<n>` for an entry or `:R<n>` for a reply, its index in",
              ' * the DLG. Conditions and actions name scripts by resref (`scripts.ts`).',
              ' *',
              HEADER,
              ' */',
              'export const KOTOR_DIALOGUES: Dialogue[] = [']
    index += [f'  {dlg}.DIALOGUE,' for _, dlg in sorted(written)]
    for name, rows, kind in (('KOTOR_DIALOGUE_NODES', 'NODES', 'DialogueNode'),
                             ('KOTOR_DIALOGUE_STARTS', 'STARTS', 'DialogueStart'),
                             ('KOTOR_DIALOGUE_LINKS', 'LINKS', 'DialogueLink')):
        index += ['];', '', f'export const {name}: {kind}[] = [']
        index += [f'  ...{dlg}.{rows},' for _, dlg in sorted(written)]
    index += ['];', '',
              'export { KOTOR_DIALOGUE_ACTIONS, KOTOR_DIALOGUE_CONDITIONS } from "./scripts";', '']
    write(os.path.join(folder, 'index.ts'), index)

    ids = ['/**', ' * Every script the dialogues name, by KOTOR resref.', ' *', HEADER, ' */', '']
    for kind, name in (('condition', 'KotorDialogueConditionId'), ('action', 'KotorDialogueActionId')):
        ids.append(f'export type {name} =')
        ids += [f'  | {q(resref)}' for resref in sorted(scripts[kind])]
        ids[-1] += ';'
        ids.append('')
    write(os.path.join(folder, 'scriptIds.ts'), ids)

    hand = ported(folder)
    stub_functions = {
        'failUnportedCondition': ['/** A condition not ported yet. */',
                                  'function failUnportedCondition(): boolean {', '  return false;',
                                  '}'],
        'failMissingCondition': ["/** A condition whose script KOTOR doesn't have, so it always"
                                 " fails there too. */",
                                 'function failMissingCondition(): boolean {', '  return false;',
                                 '}'],
        'skipUnportedAction': ['/** An action not ported yet. */',
                               'function skipUnportedAction(): void {}'],
        'skipMissingAction': ["/** An action whose script KOTOR doesn't have, so it does nothing"
                              " there either. */",
                              'function skipMissingAction(): void {}'],
    }
    tables, used, counts = [], set(), {}
    for kind, name, union, unported, missing in (
            ('condition', 'KOTOR_DIALOGUE_CONDITION_STUBS', 'KotorDialogueConditionId',
             'failUnportedCondition', 'failMissingCondition'),
            ('action', 'KOTOR_DIALOGUE_ACTION_STUBS', 'KotorDialogueActionId',
             'skipUnportedAction', 'skipMissingAction')):
        left = sorted(set(scripts[kind]) - hand[kind])
        counts[kind] = (len(scripts[kind]), len(left),
                        sum(scripts[kind][r][0] is None for r in left))
        tables.append(f'export const {name} = {{')
        for resref in left:
            stub = missing if scripts[kind][resref][0] is None else unported
            used.add(stub)
            tables.append(f'  {key(resref)}: {stub},')
        tables += [f'}} satisfies Partial<Record<{union}, unknown>>;', '']
    stubs = ['import type { KotorDialogueActionId, KotorDialogueConditionId } from "./scriptIds";',
             '',
             '/**',
             " * Stand-ins for the dialogue scripts no `scripts.ts` ports yet, and for those KOTOR",
             " * itself doesn't have: a condition that fails and an action that does nothing, as KOTOR",
             " * does with a script it can't find. Port one and rerun the generator to drop its stub.",
             ' *',
             HEADER,
             ' */',
             '']
    for stub, lines in stub_functions.items():
        if stub in used:
            stubs += lines + ['']
    write(os.path.join(folder, 'stubs.ts'), stubs + tables)

    print(f'wrote {len(written)} dialogues: {totals[0]} lines, {totals[1]} starts, '
          f'{totals[2]} links')
    for kind, (total, left, missing) in counts.items():
        print(f'{kind} scripts: {total} named, {total - left} ported, {left - missing} stubbed, '
              f'{missing} missing from the game')


if __name__ == '__main__':
    main(sys.argv[1:])
