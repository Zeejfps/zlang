"""A Manaan area's instances in one screen: creatures with their conversation, doors and triggers with their links, waypoints
(dev tooling, reads the install).

    python kotor/tools/playthrough/manaan/layout.py m26aa [creatures|doors|triggers|waypoints|placeables]...

Coordinates are the instance's own (XPosition, YPosition); a trigger prints its first corner. Names come from dialog.tlk."""
import os
import sys

sys.path.insert(0, 'kotor/tools/py')
import gffpy
import kres
import tlkpy

area = sys.argv[1]
want = set(sys.argv[2:]) or {'creatures', 'doors', 'triggers', 'waypoints', 'placeables'}
game_dir = os.environ.get('KOTOR_DIR', kres.DEFAULT_DIR)
mod = 'man' + area
entries = {}
for suffix in ('', '_s'):
    for e in kres.read_container(os.path.join(game_dir, 'modules', f'{mod}{suffix}.rim')):
        entries[(e.resref.lower(), e.ext)] = e
tlk = tlkpy.load()


def load(resref, ext):
    e = entries.get((resref.lower(), ext))
    return gffpy.read(kres.read_entry(e)) if e else None


def name_of(s):
    n = s.get('FirstName') or s.get('LocName') or s.get('LocalizedName')
    if n is None:
        return ''
    if n.strref != 0xFFFFFFFF and n.strref < len(tlk):
        return tlk.text(n.strref) or ''
    return next(iter(n.strings.values()), '') if n.strings else ''


git = load(area, 'git')
for label, kind, ext in (('Creature List', 'creatures', 'utc'), ('Door List', 'doors', 'utd'),
                         ('TriggerList', 'triggers', 'utt'), ('WaypointList', 'waypoints', 'utw'),
                         ('Placeable List', 'placeables', 'utp')):
    if kind not in want:
        continue
    print(f'== {kind}')
    for s in git.get(label, []):
        tpl = s.get('TemplateResRef', '')
        t = load(tpl, ext) if tpl else None
        tag = s.get('Tag') or (t.get('Tag') if t else '') or ''
        x = s.get('XPosition', s.get('X', 0.0))
        y = s.get('YPosition', s.get('Y', 0.0))
        extra = ''
        if t is not None and ext == 'utc':
            extra = f"conv={t.get('Conversation', '')} name={name_of(t)!r} faction={t.get('FactionID')} script={t.get('ScriptDialogue', '')}"
        elif t is not None and ext == 'utp':
            extra = f"conv={t.get('Conversation', '')} name={name_of(t)!r} use={t.get('OnUsed', '')} inv={t.get('HasInventory')}"
        elif ext in ('utd', 'utt'):
            link = s.get('LinkedToModule') or (t.get('LinkedToModule') if t else '') or ''
            to = s.get('LinkedTo') or (t.get('LinkedTo') if t else '') or ''
            enter = (t.get('OnEnter') if t and ext == 'utt' else '') or ''
            used = (t.get('OnOpen') if t and ext == 'utd' else '') or ''
            lock = f" locked={t.get('Locked')} dc={t.get('OpenLockDC')} key={t.get('KeyName')}" if ext == 'utd' and t else ''
            extra = f'to={link}/{to} enter={enter} open={used}{lock}'
            if ext == 'utt':
                geo = s.get('Geometry', [])
                if geo:
                    extra += f" corner=({geo[0].get('PointX', 0):.1f},{geo[0].get('PointY', 0):.1f})"
        print(f'  {tag!r} {tpl} ({x:.1f},{y:.1f}) {extra}')
