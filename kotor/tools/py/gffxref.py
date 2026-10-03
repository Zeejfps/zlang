"""Check what GFF fields point at: resources, 2DA rows, dialog.tlk strings (for gff-*.md).

    python kotor/tools/py/gffxref.py            run every rule over every GFF in the install

Each rule names a GFF kind, a field path (as in gffschema.py) and a check:

    res EXT...       the value (a resref) exists as a resource of one of these types, or as a
                     loose file in streamwaves/streamsounds/streammusic when EXT is that dir
    2da NAME [OFF]   the value minus OFF is a row index of NAME.2da (values in SKIP are ignored)
    tlk              a CExoLocString's strref resolves to a non-empty string in dialog.tlk

A meaning in the docs is marked confirmed when its rule hits (nearly) always. Output: per rule,
how many values were checked, how many distinct, how many missed, and a few misses.
"""

import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gffpy  # noqa: E402
import kres  # noqa: E402
import tlkpy  # noqa: E402
import twodapy  # noqa: E402

SCRIPT = ('res', 'ncs')
SKIP = {-1, 65535, 4294967295}

RULES = [
    # creatures
    ('UTC', 'TemplateResRef', ('res', 'utc')),
    ('UTC', 'Appearance_Type', ('2da', 'appearance')),
    ('UTC', 'PortraitId', ('2da', 'portraits')),
    ('UTC', 'SoundSetFile', ('2da', 'soundset')),
    ('UTC', 'Race', ('2da', 'racialtypes')),
    ('UTC', 'SubraceIndex', ('2da', 'subrace')),
    ('UTC', 'Gender', ('2da', 'gender')),
    ('UTC', 'FactionID', ('2da', 'repute')),
    ('UTC', 'WalkRate', ('2da', 'creaturespeed')),
    ('UTC', 'PerceptionRange', ('2da', 'ranges')),
    ('UTC', 'BodyBag', ('2da', 'bodybag')),
    ('UTC', 'ClassList/Class', ('2da', 'classes')),
    ('UTC', 'FeatList/Feat', ('2da', 'feat')),
    ('UTC', 'ClassList/KnownList0/Spell', ('2da', 'spells')),
    ('UTC', 'SpecAbilityList/Spell', ('2da', 'spells')),
    ('UTC', 'FirstName', ('tlk',)),
    ('UTC', 'Conversation', ('res', 'dlg')),
    ('UTC', 'Equip_ItemList/EquippedRes', ('res', 'uti')),
    ('UTC', 'ItemList/InventoryRes', ('res', 'uti')),
] + [('UTC', s, SCRIPT) for s in (
    'ScriptHeartbeat', 'ScriptOnNotice', 'ScriptSpellAt', 'ScriptAttacked', 'ScriptDamaged',
    'ScriptDisturbed', 'ScriptEndRound', 'ScriptEndDialogu', 'ScriptDialogue', 'ScriptSpawn',
    'ScriptRested', 'ScriptDeath', 'ScriptUserDefine', 'ScriptOnBlocked')] + [
    # doors and placeables
    ('UTD', 'GenericType', ('2da', 'genericdoors')),
    ('UTD', 'LocName', ('tlk',)),
    ('UTD', 'Conversation', ('res', 'dlg')),
    ('UTD', 'PortraitId', ('2da', 'portraits')),
    ('UTD', 'Faction', ('2da', 'repute')),
    ('UTD', 'TrapType', ('2da', 'traps')),
    ('UTP', 'Appearance', ('2da', 'placeables')),
    ('UTP', 'LocName', ('tlk',)),
    ('UTP', 'Conversation', ('res', 'dlg')),
    ('UTP', 'Faction', ('2da', 'repute')),
    ('UTP', 'TrapType', ('2da', 'traps')),
    ('UTP', 'ItemList/InventoryRes', ('res', 'uti')),
] + [('UTD', s, SCRIPT) for s in (
    'OnClosed', 'OnFailToOpen', 'OnHeartbeat', 'OnOpen', 'OnUserDefined', 'OnDeath', 'OnClick')] + [
    ('UTP', s, SCRIPT) for s in (
        'OnClosed', 'OnDeath', 'OnHeartbeat', 'OnMeleeAttacked', 'OnOpen', 'OnSpellCastAt',
        'OnUserDefined', 'OnEndDialogue', 'OnInvDisturbed', 'OnUsed')] + [
    # items
    ('UTI', 'BaseItem', ('2da', 'baseitems')),
    ('UTI', 'LocalizedName', ('tlk',)),
    ('UTI', 'DescIdentified', ('tlk',)),
    ('UTI', 'PropertiesList/PropertyName', ('2da', 'itempropdef')),
    ('UTI', 'PropertiesList/CostTable', ('2da', 'iprp_costtable')),
    ('UTI', 'PropertiesList/Param1', ('2da', 'iprp_paramtable')),
    ('UTI', 'PropertiesList/UpgradeType', ('2da', 'upgrade')),
    # encounters, sounds, triggers, waypoints, stores
    ('UTE', 'DifficultyIndex', ('2da', 'encdifficulty')),
    ('UTE', 'CreatureList/ResRef', ('res', 'utc')),
    ('UTE', 'CreatureList/Appearance', ('2da', 'appearance')),
    ('UTE', 'OnEntered', SCRIPT),
    ('UTE', 'LocalizedName', ('tlk',)),
    ('UTS', 'Sounds/Sound', ('res', 'wav', 'streamsounds', 'streamwaves')),
    ('UTS', 'Priority', ('2da', 'prioritygroups')),
    ('UTT', 'TrapType', ('2da', 'traps')),
    ('UTT', 'Cursor', ('2da', 'cursors')),
    ('UTT', 'LocalizedName', ('tlk',)),
    ('UTT', 'ScriptOnEnter', SCRIPT),
    ('UTT', 'ScriptOnExit', SCRIPT),
    ('UTT', 'ScriptHeartbeat', SCRIPT),
    ('UTT', 'OnClick', SCRIPT),
    ('UTW', 'Appearance', ('2da', 'waypoint')),
    ('UTW', 'MapNote', ('tlk',)),
    ('UTM', 'ItemList/InventoryRes', ('res', 'uti')),
    ('UTM', 'LocName', ('tlk',)),
    # modules and areas
    ('IFO', 'Mod_Entry_Area', ('res', 'are')),
    ('IFO', 'Mod_Area_list/Area_Name', ('res', 'are')),
    ('IFO', 'Mod_VO_ID', ('dir', 'streamwaves')),
    ('IFO', 'Mod_OnHeartbeat', SCRIPT),
    ('IFO', 'Mod_OnModLoad', SCRIPT),
    ('IFO', 'Mod_OnClientEntr', SCRIPT),
    ('IFO', 'Mod_OnPlrDeath', SCRIPT),
    ('IFO', 'Mod_OnPlrDying', SCRIPT),
    ('IFO', 'Mod_OnSpawnBtnDn', SCRIPT),
    ('IFO', 'Mod_OnAcquirItem', SCRIPT),
    ('ARE', 'Name', ('tlk',)),
    ('ARE', 'CameraStyle', ('2da', 'camerastyle')),
    ('ARE', 'LoadScreenID', ('2da', 'loadscreens')),
    ('ARE', 'Grass_TexName', ('res', 'tpc', 'tga')),
    ('ARE', 'DefaultEnvMap', ('res', 'tpc', 'tga')),
    ('ARE', 'Rooms/RoomName', ('res', 'mdl')),
    ('ARE', 'Rooms/EnvAudio', ('2da', 'soundeax')),
    ('ARE', 'OnEnter', SCRIPT),
    ('ARE', 'OnHeartbeat', SCRIPT),
    ('ARE', 'MiniGame.Player.Models/Model', ('res', 'mdl')),
    ('ARE', 'MiniGame.Enemies/Models/Model', ('res', 'mdl')),
    ('ARE', 'MiniGame.Player.Track', ('res', 'mdl')),
    ('ARE', 'MiniGame.Obstacles/Name', ('res', 'mdl')),
    ('ARE', 'MiniGame.Music', ('dir', 'streammusic')),
    ('GIT', 'AreaProperties.AmbientSndDay', ('2da', 'ambientsound')),
    ('GIT', 'AreaProperties.AmbientSndNight', ('2da', 'ambientsound')),
    ('GIT', 'AreaProperties.MusicDay', ('2da', 'ambientmusic')),
    ('GIT', 'AreaProperties.MusicNight', ('2da', 'ambientmusic')),
    ('GIT', 'AreaProperties.MusicBattle', ('2da', 'ambientmusic')),
    ('GIT', 'AreaProperties.EnvAudio', ('2da', 'soundeax')),
    ('GIT', 'Creature List/TemplateResRef', ('res', 'utc')),
    ('GIT', 'Door List/TemplateResRef', ('res', 'utd')),
    ('GIT', 'Placeable List/TemplateResRef', ('res', 'utp')),
    ('GIT', 'TriggerList/TemplateResRef', ('res', 'utt')),
    ('GIT', 'WaypointList/TemplateResRef', ('res', 'utw')),
    ('GIT', 'SoundList/TemplateResRef', ('res', 'uts')),
    ('GIT', 'Encounter List/TemplateResRef', ('res', 'ute')),
    ('GIT', 'StoreList/ResRef', ('res', 'utm')),
    ('GIT', 'List/TemplateResRef', ('res', 'uti')),
    ('GIT', 'Door List/LinkedToModule', ('res', 'ifo-module')),
    ('GIT', 'TriggerList/LinkedToModule', ('res', 'ifo-module')),
    ('GIT', 'Door List/TransitionDestin', ('tlk',)),
    ('GIT', 'WaypointList/MapNote', ('tlk',)),
    # dialogue and journal
    ('DLG', 'EntryList/Text', ('tlk',)),
    ('DLG', 'ReplyList/Text', ('tlk',)),
    ('DLG', 'EntryList/Script', SCRIPT),
    ('DLG', 'ReplyList/Script', SCRIPT),
    ('DLG', 'StartingList/Active', SCRIPT),
    ('DLG', 'EntryList/RepliesList/Active', SCRIPT),
    ('DLG', 'ReplyList/EntriesList/Active', SCRIPT),
    ('DLG', 'EndConversation', SCRIPT),
    ('DLG', 'EndConverAbort', SCRIPT),
    ('DLG', 'EntryList/VO_ResRef', ('dir', 'streamwaves')),
    ('DLG', 'ReplyList/VO_ResRef', ('dir', 'streamwaves')),
    ('DLG', 'EntryList/Sound', ('res', 'wav', 'streamwaves', 'streamsounds')),
    ('DLG', 'CameraModel', ('res', 'mdl')),
    ('DLG', 'StuntList/StuntModel', ('res', 'mdl')),
    ('DLG', 'AmbientTrack', ('dir', 'streammusic')),
    ('DLG', 'EntryList/PlotIndex', ('2da', 'plot')),
    ('DLG', 'EntryList/CamVidEffect', ('2da', 'videoeffects')),
    ('DLG', 'EntryList/AnimList/Animation', ('2da', 'dialoganimations', 10000)),
    ('DLG', 'EntryList/CameraAnimation', ('2da', 'animations', 10000)),
    ('JRL', 'Categories/Name', ('tlk',)),
    ('JRL', 'Categories/EntryList/Text', ('tlk',)),
    ('JRL', 'Categories/PlotIndex', ('2da', 'plot')),
    ('JRL', 'Categories/PlanetID', ('2da', 'planetary')),
    # GUI
    ('GUI', 'CONTROLS/BORDER.FILL', ('res', 'tpc', 'tga')),
    ('GUI', 'CONTROLS/BORDER.EDGE', ('res', 'tpc', 'tga')),
    ('GUI', 'CONTROLS/BORDER.CORNER', ('res', 'tpc', 'tga')),
    ('GUI', 'CONTROLS/TEXT.FONT', ('res', 'tpc', 'tga', 'txi')),
    ('GUI', 'CONTROLS/TEXT.STRREF', ('tlk',)),
    ('GUI', 'BORDER.FILL', ('res', 'tpc', 'tga')),
]


def all_entries(g):
    """kres's entries plus patch.erf, which kres.Game does not load but the game does (it holds
    7 GUI files that replace gui.bif's)."""
    out = list(g.entries())
    patch = os.path.join(g.dir, 'patch.erf')
    if os.path.isfile(patch) and patch not in g.containers():
        out.extend(kres.read_container(patch))
    return out


def loose_index(game_dir):
    out = {}
    for sub in ('streamwaves', 'streamsounds', 'streammusic'):
        names = set()
        dirs = set()
        for root, ds, fs in os.walk(os.path.join(game_dir, sub)):
            for d in ds:
                dirs.add(d.lower())
            for f in fs:
                names.add(os.path.splitext(f)[0].lower())
        out[sub] = (names, dirs)
    return out


def main(argv):
    g = kres.Game()
    have = set((e.resref, e.ext) for e in g.entries())
    modules = set(os.path.splitext(n)[0].lower().removesuffix('_s')
                  for n in os.listdir(os.path.join(g.dir, 'modules')))
    loose = loose_index(g.dir)
    tlk = tlkpy.load()
    tables = {}
    by_kind = defaultdict(list)
    for kind, path, check in RULES:
        by_kind[kind].append((path, check))
    seen = set()
    stats = {}  # (kind, path, check) -> [checked, distinct set, misses list, miss count]

    def check_value(check, v):
        how = check[0]
        if how == 'tlk':
            ref = v if isinstance(v, int) else v.strref
            if ref in (-1, 4294967295):
                return None
            t = tlk.text(ref)
            return bool(t)
        if how == '2da':
            if not isinstance(v, int) or v in SKIP:
                return None
            name = check[1]
            off = check[2] if len(check) > 2 else 0
            if name not in tables:
                tables[name] = twodapy.parse(g.get(name, '2da'))
            return 0 <= v - off < len(tables[name].rows)
        if how in ('res', 'dir'):
            if not isinstance(v, str):
                v = str(v)
            r = v.lower().strip()
            if r == '':
                return None
            for ext in check[1:]:
                if ext in loose:
                    names, dirs = loose[ext]
                    if (r in dirs) if how == 'dir' else (r in names):
                        return True
                    if how == 'dir' and r in names:
                        return True
                elif ext == 'ifo-module':
                    if r in modules:
                        return True
                elif (r, ext) in have:
                    return True
            return False
        raise ValueError(how)

    def walk(kind, s, prefix):
        rules = by_kind.get(kind)
        for f in s.fields:
            p = prefix + f.label
            for path, check in rules:
                if path == p:
                    ok = check_value(check, f.value)
                    if ok is None:
                        continue
                    st = stats.setdefault((kind, path, check), [0, set(), [], 0])
                    st[0] += 1
                    key = getattr(f.value, 'strref', f.value)
                    st[1].add(key)
                    if not ok:
                        st[3] += 1
                        if key not in st[2] and len(st[2]) < 6:
                            st[2].append(key)
            if f.type == 14:
                walk(kind, f.value, p + '.')
            elif f.type == 15:
                for e in f.value:
                    walk(kind, e, p + '/')

    for e in all_entries(g):
        if e.size < 56:
            continue
        with open(e.container, 'rb') as fh:
            fh.seek(e.offset)
            data = fh.read(e.size)
        if data[4:8] != b'V3.2':
            continue
        kind = data[:4].decode('latin-1').strip()
        if kind not in by_kind:
            continue
        h = hash(data)
        if h in seen:
            continue
        seen.add(h)
        walk(kind, gffpy.read(data), '')

    print(f"{'kind':5} {'field':36} {'check':28} {'values':>7} {'distinct':>8} {'missed':>7}  misses")
    for kind, path, check in RULES:
        st = stats.get((kind, path, check))
        c = ' '.join(str(x) for x in check)
        if st is None:
            print(f'{kind:5} {path:36} {c:28} {0:7} {0:8} {0:7}')
            continue
        print(f'{kind:5} {path:36} {c:28} {st[0]:7} {len(st[1]):8} {st[3]:7}  {st[2]}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
