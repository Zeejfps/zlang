"""A conversation as a tree with its texts: dlg_tree.py DUMP.txt [DEPTH]
DUMP.txt is `sh kotor/tools/playthrough/dump.sh MODULE NAME dlg > DUMP.txt` (the GFF dump of the DLG). Prints the starting entries
and, indented, what each node says (E = NPC entry, R = player reply), its script, quest/journal entry and PlotIndex, the
`Active` condition script of each link, and for a reply the number the reply queue (`ui replies`) counts: its position among
the replies the player is offered (conditions that fail hide replies in play, so the number is for the case that they all pass).
Dev tooling for writing `ui replies` lines of a playthrough."""
import re
import sys

sys.path.insert(0, 'kotor/tools/py')
import tlkpy

t = tlkpy.load()
lines = open(sys.argv[1], encoding='utf-8').read().split('\n')
depth_max = int(sys.argv[2]) if len(sys.argv) > 2 else 8


def parse():
    lists = {}
    cur = None  # (listname, index)
    sub = None
    node = None
    for l in lines:
        m = re.match(r'  (EntryList|ReplyList|StartingList): List\[(\d+)\]', l)
        if m:
            cur = m.group(1)
            lists[cur] = []
            sub = None
            continue
        if re.match(r'  \w+: ', l) and not l.startswith('   '):
            if not re.match(r'  (EntryList|ReplyList|StartingList)', l):
                cur = None
            continue
        if cur is None:
            continue
        m = re.match(r'    \[(\d+)\] id \d+', l)
        if m:
            node = {'links': [], 'text': '', 'script': '', 'quest': '', 'plot': '', 'speaker': ''}
            lists[cur].append(node)
            sub = None
            continue
        if node is None:
            continue
        m = re.match(r'      Text: CExoLocString = strref (-?\d+)', l)
        if m:
            n = int(m.group(1))
            node['text'] = (t.text(n) or '') if n >= 0 else ''
            continue
        m = re.match(r'      Text: CExoLocString = .*"(.*)"', l)
        if m and not node['text']:
            node['text'] = m.group(1)
        m = re.match(r'      Script: CResRef = "(.*)"', l)
        if m:
            node['script'] = m.group(1)
        m = re.match(r'      Quest: CExoString = "(.*)"', l)
        if m:
            node['quest'] = m.group(1)
        m = re.match(r'      QuestEntry: DWORD = (\d+)', l)
        if m:
            node['quest'] += ':' + m.group(1)
        m = re.match(r'      Speaker: CExoString = "(.*)"', l)
        if m:
            node['speaker'] = m.group(1)
        m = re.match(r'      (RepliesList|EntriesList): List', l)
        if m:
            sub = 'links'
            continue
        m = re.match(r'          Index: DWORD = (\d+)', l)
        if m and sub:
            node['links'].append({'index': int(m.group(1)), 'active': ''})
            continue
        m = re.match(r'          Active: CResRef = "(.*)"', l)
        if m and sub and node['links']:
            node['links'][-1]['active'] = m.group(1)
        m = re.match(r'      Index: DWORD = (\d+)', l)
        if m and cur == 'StartingList':
            node['links'].append({'index': int(m.group(1)), 'active': ''})
        m = re.match(r'      Active: CResRef = "(.*)"', l)
        if m and cur == 'StartingList' and node['links']:
            node['links'][-1]['active'] = m.group(1)
    return lists


L = parse()
E = L.get('EntryList', [])
R = L.get('ReplyList', [])
seen = set()


def show(kind, i, depth, pick):
    n = (E if kind == 'E' else R)[i]
    txt = n['text'].replace('\n', ' ')[:110]
    extra = ''
    if n['script']:
        extra += ' [script %s]' % n['script']
    if n['quest'] and n['quest'] != ':0':
        extra += ' [quest %s]' % n['quest']
    pre = '  ' * depth
    tag = '%s%d' % (kind, i)
    if pick:
        tag += ' (#%d)' % pick
    again = (kind, i) in seen
    print('%s%s %s"%s"%s%s' % (pre, tag, (n['speaker'] + ': ') if n['speaker'] else '', txt, extra, '  ...' if again and n['links'] else ''))
    if again or depth >= depth_max:
        return
    seen.add((kind, i))
    for k, link in enumerate(n['links']):
        cond = ' if %s' % link['active'] if link['active'] else ''
        if cond:
            print('%s  |%s' % (pre, cond))
        show('R' if kind == 'E' else 'E', link['index'], depth + 1, (k + 1) if kind == 'E' else 0)


starts = L.get('StartingList', [])
for s in starts:
    for k, link in enumerate(s['links']):
        cond = ' if %s' % link['active'] if link['active'] else ''
        print('START%s' % cond)
        show('E', link['index'], 1, 0)
