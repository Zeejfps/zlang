"""A conversation as an indented tree: who says what, which script decides each link, which fire.

    python kotor/tools/py/dlgtree.py RESREF [--width N] [--journal CATEGORY]

Entries (E) are the NPC's lines, replies (R) the player's. A link prints its condition script as
`?script` (`!` when the link is negated), a node its action script as `{script}`, a journal update
as `[J category:entry]` and plot XP as `[xp %]`. A node reached a second time prints as `(= E12)`
instead of repeating its subtree. For reading the data while playing it: not used by the game.

    python kotor/tools/py/dlgtree.py kas23_chuunda_01
    python kotor/tools/py/dlgtree.py --journal kas23_mainwookplot      the journal category's entries
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import gffpy  # noqa: E402
import kres  # noqa: E402
import tlkpy  # noqa: E402

TLK = None
GAME = None


def text_of(loc, width):
    global TLK
    if TLK is None:
        TLK = tlkpy.load()
    s = ''
    if loc.strref != 0xFFFFFFFF and loc.strref < len(TLK):
        s = TLK.text(loc.strref) or ''
    if not s and loc.strings:
        s = next(iter(loc.strings.values()))
    s = s.replace('\n', ' ')
    return s if len(s) <= width else s[:width] + '...'


def link(node_list, kind):
    out = []
    for l in node_list:
        out.append((l['Index'], l.get('Active', ''), l.get('Not', 0) if 'Not' in [f.label for f in l.fields] else 0))
    return out


def show(dlg, width):
    entries = dlg['EntryList']
    replies = dlg['ReplyList']
    seen = set()

    def node(kind, idx, depth):
        pad = '  ' * depth
        n = (entries if kind == 'E' else replies)[idx]
        key = (kind, idx)
        label = f'{kind}{idx}'
        speaker = n.get('Speaker', '') if kind == 'E' else ''
        tag = f' <{speaker}>' if speaker else ''
        if key in seen:
            print(f'{pad}(= {label}){tag}')
            return
        seen.add(key)
        extras = ''
        if n.get('Script'):
            extras += f' {{{n["Script"]}}}'
        if n.get('Quest'):
            extras += f' [J {n["Quest"]}:{n.get("QuestEntry", "?")}]'
        if n.get('PlotIndex', -1) != -1 or n.get('PlotXPPercentage', 1.0) != 1.0:
            extras += f' [xp {n.get("PlotXPPercentage", 1.0)}]'
        print(f'{pad}{label}{tag} "{text_of(n["Text"], width)}"{extras}')
        children = n.get('RepliesList' if kind == 'E' else 'EntriesList', [])
        for c in children:
            cond = c.get('Active', '')
            cnot = ''
            for f in c.fields:
                if f.label == 'Not' or f.label == 'Active2':
                    pass
            neg = c.get('ActiveNot', 0) if 'ActiveNot' in c.labels() else 0
            mark = f' ?{"!" if neg else ""}{cond}' if cond else ''
            ck = 'R' if kind == 'E' else 'E'
            child = (replies if kind == 'E' else entries)[c['Index']]
            if mark:
                print(f'{pad}  ->{mark}')
            node(ck, c['Index'], depth + 1)

    print(f'{len(entries)} entries, {len(replies)} replies; end script {dlg.get("EndConversation", "")!r} '
          f'abort {dlg.get("EndConverAbort", "")!r}')
    for s in dlg['StartingList']:
        cond = s.get('Active', '')
        print(f'START E{s["Index"]}' + (f' ?{cond}' if cond else ''))
    for s in dlg['StartingList']:
        node('E', s['Index'], 1)


def show_journal(cat, width):
    global GAME
    data = GAME.get('global', 'jrl')
    root = gffpy.read(data)
    for c in root['Categories']:
        if c['Tag'].lower() == cat.lower():
            print(f'{c["Tag"]} "{text_of(c["Name"], width)}" priority {c.get("Priority")} xp {c.get("PlotIndex")}')
            for e in sorted(c['EntryList'], key=lambda e: e['ID']):
                print(f'  {e["ID"]:>4}{" END" if e.get("End") else "    "} xp {e.get("XP_Percentage", 0)}: {text_of(e["Text"], width)}')
            return
    print('no such category')


def main(argv):
    global GAME
    width = 110
    rest = []
    journal = None
    module = None       # the copy that module's rim holds (a few conversations exist in several modules)
    i = 0
    while i < len(argv):
        if argv[i] == '--width':
            width = int(argv[i + 1])
            i += 2
        elif argv[i] == '--journal':
            journal = argv[i + 1]
            i += 2
        elif argv[i] == '--module':
            module = argv[i + 1].lower()
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    GAME = kres.Game()
    if journal:
        show_journal(journal, width)
        return
    for name in rest:
        found = GAME.find(name.lower(), 'dlg')
        if module:
            found = [e for e in found if os.path.basename(e.container).lower().startswith(module)]
        data = kres.read_entry(found[-1]) if found else None
        if data is None:
            print(f'{name}: not found')
            continue
        show(gffpy.read(data), width)


if __name__ == '__main__':
    main(sys.argv[1:])
