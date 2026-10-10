"""Convert KOTOR dialogues into another_game_framework's dialogue files (JSON), for its editor.

    python kotor/tools/py/agf_dialogue_json.py [--agf DIR] [--force] [RESREF ...]

Writes `apps/kotor/dialogues/<planet>/<resref>.json` in the framework repo (default
G:/Dev/another_game_framework) for each conversation (DLG) named, or DIALOGUES. Once written, a
file is the framework's to edit, so an existing one is left alone unless --force.

A file holds the dialogue's starts and lines, in the DLG's order, as the framework's dialogue
tables do, with the ids local to the file (`E<n>` for an entry, `R<n>` for a reply, its index in
the DLG):

- `owner`: the tag of the creature or placeable whose template names this conversation, when
  exactly one does; a line with no speaker, or with this tag, is the owner's.
- `speakers`: a name for each speaker tag the lines use, and the owner's, from the creature (or
  placeable) templates: the module's first, then the game's.
- `starts`: `{entryNodeId, conditionId?, kotor?}`, the first passing wins.
- `nodes`: `{id, kind, speaker?, listener?, text, questEntryId?, actionId?, comment?, links,
  kotor?}`; `links` are `{toNodeId, conditionId?, comment?, kotor?}` in order.
- `kotor`: on the dialogue, a line or a link, the DLG's other fields as they are (voice, camera,
  animations, timing, plot XP, `IsChild`), leaving out empty strings and lists and known
  defaults, plus `strref` for a line's text, and the dialogue's `module` and `missingScripts`
  (scripts it names that the game doesn't have).

Formatted as `JSON.stringify(file, null, 2)` formats it, so the editor can write the same bytes.
"""
import argparse
import json
import os
import struct
import sys

import gffpy
import kres
import tlkpy
from agf_containers import DEFAULT_AGF, Install
from agf_dialogues import (PLANETS, find_dialogue, module_resources, quest_states, read_script,
                           text_of)

DIALOGUES = ['tar02_zelka021', 'tar02_gurney021', 'tar03_zax031', 'tar11_gadon112',
             'dan14_bolook', 'man26_trial']

# Fields the file names itself, or that hold the graph.
MAPPED = {'Text', 'Script', 'Speaker', 'Listener', 'Quest', 'QuestEntry', 'Comment',
          'EntriesList', 'RepliesList', 'Index', 'Active', 'LinkComment',
          'EntryList', 'ReplyList', 'StartingList'}
# A field at this value says nothing (dialogue.md 3).
DEFAULTS = {'WaitFlags': 0, 'CameraAngle': 0, 'FadeType': 0, 'IsChild': 0, 'PlotIndex': -1}


def number(v):
    """A float as the shortest decimal its float32 round-trips through, an int when whole."""
    if not isinstance(v, float):
        return v
    packed = struct.pack('<f', v)
    for p in range(1, 10):
        s = float(f'{v:.{p}g}')
        if struct.pack('<f', s) == packed:
            return int(s) if s.is_integer() else s
    return v


def value(v, tlk):
    if isinstance(v, gffpy.Struct):
        return extra(v, tlk, set())
    if isinstance(v, (list, tuple)):
        return [value(x, tlk) for x in v]
    if isinstance(v, bytes):
        return v.hex()
    if hasattr(v, 'strref'):
        return text_of(tlk, v)
    return number(v)


def extra(s, tlk, skip):
    """The struct's fields not named elsewhere, leaving out empty and default values."""
    out = {}
    for f in s.fields:
        if f.label in skip or f.label in MAPPED:
            continue
        if f.value in ('', []) or DEFAULTS.get(f.label, object()) == f.value:
            continue
        out[f.label] = value(f.value, tlk)
    if 'PlotIndex' not in out:
        out.pop('PlotXPPercentage', None)
    return out


def template_name(tlk, s, ext):
    """A creature template's first and last name, or a placeable's name."""
    labels = ('FirstName', 'LastName') if ext == 'utc' else ('LocName',)
    parts = [text_of(tlk, s[label]) for label in labels if s.get(label) is not None]
    return ' '.join(part for part in parts if part).strip()


def index_templates(install, keyed, tlk):
    """The creature and placeable templates' tags, names and conversations: per module
    (module -> [(tag, name, conversation)]), and the game's own, from the BIFs."""
    modules = {}
    for mod, files in install.modules().items():
        rows = []
        for f in files:
            for e in kres.read_container(f):
                if e.ext in ('utc', 'utp'):
                    t = gffpy.read(kres.read_entry(e))
                    rows.append(((t.get('Tag') or ''), template_name(tlk, t, e.ext),
                                 (t.get('Conversation') or '').lower()))
        modules[mod] = rows
    game = []
    for e in keyed:
        if e.ext == 'utc':
            t = gffpy.read(kres.read_entry(e))
            game.append(((t.get('Tag') or ''), template_name(tlk, t, e.ext), ''))
    return modules, game


def find_owner(templates, mod, dlg):
    """The tag of the one template in the module naming the conversation, else None."""
    tags = {tag for tag, _, conversation in templates[mod] if conversation == dlg}
    return tags.pop() if len(tags) == 1 else None


def name_speakers(templates, game, mod, tags):
    """A name for each tag: the first template with it, the module's before the game's."""
    names = {}
    for tag in tags:
        for row_tag, name, _ in [*templates[mod], *game]:
            if row_tag.lower() == tag.lower() and name:
                names[tag] = name
                break
    return names


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--agf', default=DEFAULT_AGF, help='the framework repo')
    ap.add_argument('--force', action='store_true', help='overwrite existing files')
    ap.add_argument('dialogues', nargs='*', default=DIALOGUES)
    args = ap.parse_args(argv)

    install = Install()
    keyed = kres.read_key(install.game.dir)
    chitin = {e.resref: e for e in keyed if e.ext == 'ncs'}
    quests = quest_states({(e.resref, e.ext): e for e in keyed})
    tlk = tlkpy.load()
    resources = module_resources(install)
    templates, game = index_templates(install, keyed, tlk)
    folder = os.path.join(args.agf, 'apps', 'kotor', 'dialogues')

    for dlg in args.dialogues:
        mod, root = find_dialogue(resources, dlg)
        path = os.path.join(folder, PLANETS[mod[:3]], f'{dlg}.json')
        if os.path.exists(path) and not args.force:
            print(f'kept {path}: it exists')
            continue
        missing = set()

        def script(resref):
            resref = (resref or '').lower()
            if resref and read_script(chitin, resources[mod], resref) is None:
                missing.add(resref)
            return resref

        def link(l, prefix):
            out = {'toNodeId': f'{prefix}{l["Index"]}'}
            condition = script(l.get('Active'))
            if condition:
                out['conditionId'] = condition
            if l.get('LinkComment'):
                out['comment'] = l['LinkComment']
            kotor = extra(l, tlk, set())
            if kotor:
                out['kotor'] = kotor
            return out

        nodes = []
        for kind, prefix, lst, child_list, child_prefix in (
                ('entry', 'E', 'EntryList', 'RepliesList', 'R'),
                ('reply', 'R', 'ReplyList', 'EntriesList', 'E')):
            for i, n in enumerate(root[lst]):
                node = {'id': f'{prefix}{i}', 'kind': kind}
                for field, key in (('Speaker', 'speaker'), ('Listener', 'listener')):
                    if n.get(field):
                        node[key] = n[field]
                node['text'] = text_of(tlk, n['Text'])
                quest, state = (n.get('Quest') or '').lower(), n.get('QuestEntry') or 0
                if quest and state != 0:
                    if state not in quests.get(quest, ()):
                        raise SystemExit(f'{dlg} {prefix}{i} names {quest} {state}, '
                                         'not in global.jrl')
                    node['questEntryId'] = f'{quest}:{state}'
                action = script(n.get('Script'))
                if action:
                    node['actionId'] = action
                if n.get('Comment'):
                    node['comment'] = n['Comment']
                node['links'] = [link(l, child_prefix) for l in n.get(child_list) or []]
                kotor = extra(n, tlk, set())
                if 0 <= n['Text'].strref < 0xFFFFFFFF:
                    kotor = {'strref': n['Text'].strref, **kotor}
                if kotor:
                    node['kotor'] = kotor
                nodes.append(node)
        starts = []
        for s in root['StartingList']:
            start = link(s, 'E')
            starts.append({'entryNodeId': start.pop('toNodeId'), **start})
        kotor = {'module': mod, **extra(root, tlk, {'NumWords'})}
        if missing:
            kotor['missingScripts'] = sorted(missing)
        owner = find_owner(templates, mod, dlg)
        tags = {node['speaker'] for node in nodes if 'speaker' in node}
        if owner is not None:
            tags.add(owner)
        speakers = name_speakers(templates, game, mod, sorted(tags))
        out = {'id': dlg}
        if owner is not None:
            out['owner'] = owner
        out.update({'speakers': speakers, 'starts': starts, 'nodes': nodes, 'kotor': kotor})
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
        unnamed = sorted(tags - set(speakers))
        print(f'wrote {path}: {len(nodes)} lines, {len(starts)} starts, owner {owner}, '
              f'{len(speakers)} speakers named' + (f', unnamed: {unnamed}' if unnamed else ''))


if __name__ == '__main__':
    main(sys.argv[1:])
