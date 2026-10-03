"""Inventory every 2DA in the install: parse each copy, compare copies, profile every column, and
check the cross-references between tables, resources, dialog.tlk, GFF fields, walkmesh materials,
nwscript.nss constants and (when kotor/re/bin/swkotor_unpacked.exe exists) the exe's strings.

    python kotor/tools/py/twoda_catalog.py [--out DIR] [--no-gff]

Writes DIR/2da-inventory.json and DIR/2da-inventory.txt (default kotor/extract/) and prints a
summary: entries read, parse failures, tables with several copies and how the copies differ, and
the hit rate of every check below. docs/formats/2da-catalog.md quotes this summary.

Which copy is profiled: patch.erf's when there is one (the shipped update), else the BIF's (the
RIM copies have the same cells; see twodapy's docstring).

Column profile: non-empty cells, distinct values, a kind (int, float, hex, string, empty), and for
  int columns:    min/max; for columns whose name suggests text (name, desc, strref, ...) the share
                  of values that resolve to non-empty text in dialog.tlk
  string columns: the share of distinct values that exist as a resource of each type (best few),
                  and the share that name a 2DA.
"""

import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres      # noqa: E402
import tlkpy     # noqa: E402
import twodapy   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.normpath(os.path.join(HERE, '..', '..', 'extract'))

INT_RE = re.compile(r'^-?\d+$')
HEX_RE = re.compile(r'^0x[0-9a-fA-F]+$')
FLOAT_RE = re.compile(r'^-?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?f?$')
RESREF_RE = re.compile(r'^[A-Za-z0-9_\-]{1,16}$')
TEXTY_RE = re.compile(r'name|desc|str|text|hint|message|tooltip|title')

# Loose folders the engine reads files from by name (not inside KEY/ERF/RIM containers).
LOOSE_DIRS = ('streammusic', 'streamsounds', 'streamwaves', 'movies', 'modules', 'TexturePacks',
              'lips')

TEX = ['tpc', 'tga']

# Cross-reference checks: (table, column, kind, arg). column '#label' means the row labels.
#   res      arg = (types, pattern): pattern.format(value) exists as one of the resource types
#   row      arg = table: integer value is a row index of it (-1 and empty mean none)
#   label    arg = table: value equals a row label of it
#   match    arg = (table, column): value equals some cell of that column (case-insensitive)
#   col      arg = (table, pattern): pattern.format(value) is a column label of that table
#   colnum   arg = table: some column label of it starts with "<value>_"
#   rowlist  arg = table: value is '_'-separated row indices of it
#   strref   value resolves to non-empty text in dialog.tlk
#   2da      arg = pattern: pattern.format(value) names a 2DA in the install
#   module   value names a module in modules/ (<name>.rim or <name>.mod)
CHECKS = [
    # appearance and models
    ('appearance', 'string_ref', 'strref', None),
    ('appearance', 'race', 'res', (['mdl'], '{}')),
    ('appearance', 'racetex', 'res', (TEX, '{}')),
] + [('appearance', 'model' + c, 'res', (['mdl'], '{}')) for c in 'abcdefghij'] + [
    ('appearance', 'tex' + c, 'res', (TEX, '{}01')) for c in 'abcdefghij'] + [
    ('appearance', 'texaevil', 'res', (TEX, '{}01')),
    ('appearance', 'envmap', 'res', (TEX, '{}')),
    ('appearance', 'normalhead', 'row', 'heads'),
    ('appearance', 'backuphead', 'row', 'heads'),
    ('appearance', 'portrait', 'res', (TEX, '{}')),
    ('appearance', 'moverate', 'match', ('creaturespeed', '2daname')),
    ('appearance', 'racialtype', 'row', 'racialtypes'),
    ('appearance', 'sizecategory', 'row', 'creaturesize'),
    ('appearance', 'footsteptype', 'row', 'footstepsounds'),
    ('appearance', 'soundapptype', 'row', 'appearancesndset'),
    ('appearance', 'body_bag', 'row', 'bodybag'),
    ('appearance', 'freelookeffect', 'row', 'videoeffects'),
    ('appearance', 'deathvfx', 'label', 'visualeffects'),
    ('heads', 'head', 'res', (['mdl'], '{}')),
    ('heads', 'headtexe', 'res', (TEX, '{}')),
    ('heads', 'headtexve', 'res', (TEX, '{}')),
    ('heads', 'headtexvve', 'res', (TEX, '{}')),
    ('heads', 'headtexvvve', 'res', (TEX, '{}')),
    ('portraits', 'baseresref', 'res', (TEX, '{}')),
    ('portraits', 'baseresrefe', 'res', (TEX, '{}')),
    ('portraits', 'baseresrefve', 'res', (TEX, '{}')),
    ('portraits', 'baseresrefvve', 'res', (TEX, '{}')),
    ('portraits', 'baseresrefvvve', 'res', (TEX, '{}')),
    ('portraits', 'appearancenumber', 'row', 'appearance'),
    ('portraits', 'appearance_s', 'row', 'appearance'),
    ('portraits', 'appearance_l', 'row', 'appearance'),
    ('portraits', 'race', 'row', 'racialtypes'),
    ('portraits', 'sex', 'row', 'gender'),
    ('placeables', 'strref', 'strref', None),
    ('placeables', 'modelname', 'res', (['mdl'], '{}')),
    ('placeables', 'soundapptype', 'row', 'placeableobjsnds'),
    ('placeables', 'bodybag', 'row', 'bodybag'),
    ('genericdoors', 'strref', 'strref', None),
    ('genericdoors', 'modelname', 'res', (['mdl'], '{}')),
    ('genericdoors', 'soundapptype', 'row', 'placeableobjsnds'),
    ('doortypes', 'model', 'res', (['mdl'], '{}')),
    ('doortypes', 'templateresref', 'res', (['utd'], '{}')),
    ('doortypes', 'stringrefgame', 'strref', None),
    ('doortypes', 'soundapptype', 'row', 'placeableobjsnds'),
    ('placeableobjsnds', 'armortype', 'col', ('weaponsounds', '{}0')),
] + [('placeableobjsnds', c, 'res', (['wav'], '{}'))
     for c in ('opened', 'closed', 'destroyed', 'used', 'locked')] + [
    ('bodybag', 'name', 'strref', None),
    ('bodybag', 'appearance', 'row', 'placeables'),
    ('waypoint', 'resref', 'res', (['mdl'], '{}')),
    ('forceshields', 'visualeffectdef', 'label', 'visualeffects'),
] + [('forceshields', f'visualeffect_0{i}', 'label', 'visualeffects') for i in range(1, 5)] + [
    ('forceshields', f'appearance_0{i}', 'row', 'appearance') for i in range(1, 5)] + [
    # rules
    ('classes', 'name', 'strref', None),
    ('classes', 'description', 'strref', None),
    ('classes', 'icon', 'res', (TEX, '{}')),
    ('classes', 'attackbonustable', '2da', '{}'),
    ('classes', 'savingthrowtable', '2da', '{}'),
    ('classes', 'featstable', 'col', ('feat', '{}_list')),
    ('classes', 'skillstable', 'col', ('skills', '{}_class')),
    ('classes', 'featgain', 'col', ('featgain', '{}_reg')),
    ('classes', 'armorclasscolumn', 'col', ('acbonus', '{}')),
    ('classes', 'spellgaintable', 'col', ('classpowergain', '{}')),
    ('feat', 'name', 'strref', None),
    ('feat', 'description', 'strref', None),
    ('feat', 'icon', 'res', (TEX, '{}')),
    ('feat', 'prereqfeat1', 'row', 'feat'),
    ('feat', 'prereqfeat2', 'row', 'feat'),
    ('feat', 'successor', 'row', 'feat'),
    ('feat', 'masterfeat', 'row', 'masterfeats'),
    ('masterfeats', 'strref', 'strref', None),
    ('spells', 'name', 'strref', None),
    ('spells', 'spelldesc', 'strref', None),
    ('spells', 'iconresref', 'res', (TEX, '{}')),
    ('spells', 'impactscript', 'res', (['ncs'], '{}')),
    ('spells', 'prerequisites', 'rowlist', 'spells'),
    ('spells', 'casthandvisual', 'res', (['mdl'], '{}')),
    ('spells', 'castsound', 'res', (['wav'], '{}')),
    ('spells', 'projmodel', 'res', (['mdl'], '{}')),
    ('skills', 'name', 'strref', None),
    ('skills', 'description', 'strref', None),
    ('skills', 'icon', 'res', (TEX, '{}')),
    ('racialtypes', 'name', 'strref', None),
    ('racialtypes', 'appearance', 'row', 'appearance'),
    ('gender', 'name', 'strref', None),
    ('baseitems', 'name', 'strref', None),
    ('baseitems', 'defaultmodel', 'res', (['mdl'], '{}')),
    ('baseitems', 'defaulticon', 'res', (TEX, '{}')),
    ('baseitems', 'itemclass', 'res', (TEX, 'i{}_001')),
    ('baseitems', 'invsoundtype', 'row', 'inventorysnds'),
    ('baseitems', 'weaponmattype', 'row', 'weaponsounds'),
    ('baseitems', 'ammunitiontype', 'row', 'ammunitiontypes'),
    ('baseitems', 'reqfeat0', 'row', 'feat'),
    ('baseitems', 'reqfeat1', 'row', 'feat'),
    ('baseitems', 'reqfeat2', 'row', 'feat'),
    ('baseitems', 'specfeat', 'row', 'feat'),
    ('baseitems', 'focfeat', 'row', 'feat'),
    ('baseitems', 'propcolumn', 'colnum', 'itemprops'),
    ('baseitems', 'bodyvar', 'col', ('appearance', 'model{}')),
    ('baseitems', 'armortype', 'col', ('weaponsounds', '{}0')),
    ('baseitems', 'powerupsnd', 'res', (['wav'], '{}')),
    ('baseitems', 'powerdownsnd', 'res', (['wav'], '{}')),
    ('baseitems', 'poweredsnd', 'res', (['wav'], '{}')),
    ('itempropdef', 'name', 'strref', None),
    ('itempropdef', 'subtyperesref', '2da', '{}'),
    ('itempropdef', 'costtableresref', 'row', 'iprp_costtable'),
    ('itempropdef', 'param1resref', 'row', 'iprp_paramtable'),
    ('itemprops', 'stringref', 'strref', None),
    ('iprp_costtable', 'name', '2da', '{}'),
    ('iprp_paramtable', 'name', 'strref', None),
    ('iprp_paramtable', 'tableresref', '2da', '{}'),
    ('iprp_ammotype', 'ammotype', 'row', 'baseitems'),
    ('iprp_spells', 'spellindex', 'row', 'spells'),
    ('iprp_spells', 'icon', 'res', (TEX, '{}')),
    ('iprp_spellcost', 'spellindex', 'row', 'spells'),
    ('iprp_onhit', 'param1resref', 'row', 'iprp_paramtable'),
    ('iprp_monsterhit', 'param1resref', 'row', 'iprp_paramtable'),
    ('upgrade', 'template', 'res', (['uti'], '{}')),
    ('upgrade', 'upgradetype', 'row', 'upgradetypes'),
    ('upcrystals', 'template', 'res', (['uti'], '{}')),
    ('upcrystals', 'shortmdlvar', 'res', (['uti'], '{}')),
    ('upcrystals', 'longmdlvar', 'res', (['uti'], '{}')),
    ('upcrystals', 'doublemdlvar', 'res', (['uti'], '{}')),
    ('traps', 'trapname', 'strref', None),
    ('traps', 'name', 'strref', None),
    ('traps', 'trapscript', 'res', (['ncs'], '{}')),
    ('traps', 'resref', 'res', (['uti'], '{}')),
    ('traps', 'model', 'res', (['mdl'], '{}')),
    ('traps', 'explosionsound', 'res', (['wav'], '{}')),
    ('poison', 'name', 'strref', None),
    ('effecticon', 'iconresref', 'res', (TEX, '{}')),
    ('effecticons', 'icon', 'res', (TEX, '{}')),
    ('encdifficulty', 'strref', 'strref', None),
    ('difficultyopt', 'name', 'strref', None),
    ('feedbacktext', 'strref', 'strref', None),
    ('aiscripts', 'name_strref', 'strref', None),
    ('aiscripts', 'description_strref', 'strref', None),
    ('statescripts', 'scriptname', 'res', (['ncs'], '{}')),
    ('stringtokens', 'strref1', 'strref', None),
    ('stringtokens', 'strref2', 'strref', None),
    # world: sound, music, surfaces, effects, camera
    ('surfacemat', 'name', 'col', ('footstepsounds', '{}0')),
    ('grenadesnd', 'sound', 'res', (['wav'], '{}')),
] + [('footstepsounds', c + n, 'res', (['wav'], '{}'))
     for c in ('dirt', 'grass', 'stone', 'wood', 'water', 'carpet', 'metal', 'puddles', 'leaves')
     for n in '012'] + [
    ('footstepsounds', 'rolling', 'res', (['wav'], '{}')),
    ('footstepsounds', 'force1', 'res', (['wav'], '{}')),
    ('appearancesndset', 'armortype', 'col', ('weaponsounds', '{}0')),
    ('appearancesndset', 'weapon', 'row', 'weaponsounds'),
] + [('appearancesndset', c, 'res', (['wav'], '{}'))
     for c in ('falldirt', 'fallhard', 'fallmetal', 'fallwater')] + [
    ('weaponsounds', c, 'res', (['wav'], '{}'))
    for c in ('cloth0', 'leather0', 'armor0', 'forcefield0', 'metal0', 'wood0', 'stone0', 'parry0',
              'swingshort0', 'swinglong0', 'swingtwirl0', 'clash0')] + [
    ('ammunitiontypes', c, 'res', (['mdl'], '{}')) for c in ('model', 'model0', 'model1', 'muzzleflash')] + [
    ('ammunitiontypes', c, 'res', (['wav'], '{}'))
    for c in ('shotsound0', 'shotsound1', 'impactsound0', 'impactsound1')] + [
    ('inventorysnds', 'inventorysound', 'res', (['wav'], '{}')),
    ('ambientmusic', 'description', 'strref', None),
    ('ambientmusic', 'resource', 'res', (['wav'], '{}')),
    ('ambientmusic', 'stinger1', 'res', (['wav'], '{}')),
    ('ambientsound', 'description', 'strref', None),
    ('ambientsound', 'resource', 'res', (['wav'], '{}')),
    ('guisounds', 'soundresref', 'res', (['wav'], '{}')),
    ('aliensound', 'filename', 'res', (['wav'], '{}')),
    ('soundset', 'resref', 'res', (['ssf'], '{}')),
    ('soundset', 'strref', 'strref', None),
    ('visualeffects', 'imp_headcon_node', 'res', (['mdl'], '{}')),
    ('visualeffects', 'imp_impact_node', 'res', (['mdl'], '{}')),
    ('visualeffects', 'imp_root_m_node', 'res', (['mdl'], '{}')),
    ('visualeffects', 'soundimpact', 'res', (['wav'], '{}')),
    ('visualeffects', 'soundduration', 'res', (['wav'], '{}')),
    ('visualeffects', 'soundcessastion', 'res', (['wav'], '{}')),
    ('combatanimations', '#label', 'row', 'animations'),
] + [('combatanimations', f'{k}{i}', 'row', 'animations')
     for k in ('parry', 'dodge', 'damage') for i in range(9)] + [
    ('droiddischarge', '#label', 'match', ('appearance', 'race')),
    ('camerastyle', 'name', None, None),
    # game, GUI, modules, movies
    ('loadscreens', '#label', 'module', None),
    ('loadscreens', 'bmpresref', 'res', (TEX, '{}')),
    ('loadscreens', 'musicresref', 'res', (['wav'], '{}')),
    ('loadscreenhints', 'gameplayhint', 'strref', None),
    ('loadscreenhints', 'storyhint', 'strref', None),
    ('modulesave', '#label', 'module', None),
    ('modulesave', 'areaname', 'strref', None),
    ('minglobalrim', 'moduleresref', 'module', None),
    ('movies', '#label', 'res', (['bik'], '{}')),
    ('movies', 'strrefname', 'strref', None),
    ('credits', 'name', 'strref', None),
    ('tutorial', 'message0', 'strref', None),
    ('tutorial', 'message1', 'strref', None),
    ('tutorial', 'icon', 'res', (TEX, '{}')),
    ('planetary', 'name', 'strref', None),
    ('planetary', 'description', 'strref', None),
    ('planetary', 'icon', 'res', (TEX, '{}')),
    ('planetary', 'model', 'res', (['mdl'], '{}')),
    ('texpacks', 'texture', 'res', (['erf'], '{}')),
    ('texpacks', 'gui', 'res', (['erf'], '{}')),
    ('texpacks', 'strrefname', 'strref', None),
    ('cursors', 'resref', 'res', (TEX, '{}')),
    ('comptypes', 'computerbackground', 'res', (TEX, '{}')),
    ('bindablekeys', 'keynamestrref', 'strref', None),
    ('keymap', 'actionstrref', 'strref', None),
    ('keymap', 'descstrref', 'strref', None),
    ('npc', 'tag', None, None),
    # NWN leftovers, checked to show they point at nothing in KOTOR
    ('chargenclothes', 'itemresref', 'res', (['uti'], '{}')),
    ('hen_companion', 'baseresref', 'res', (['utc'], '{}')),
    ('hen_familiar', 'baseresref', 'res', (['utc'], '{}')),
    ('soundtypes', 'templateresref', 'res', (['uts'], '{}')),
    ('areaeffects', 'onenter', 'res', (['ncs'], '{}')),
    ('disease', '24_hour_script', 'res', (['ncs'], '{}')),
    ('domains', 'icon', 'res', (TEX, '{}')),
    ('actions', 'iconresref', 'res', (TEX, '{}')),
]

# GFF fields that index 2DA rows: (resource type, field path, table, sentinel meaning "none").
# Paths use '/' for structs and '[]' for list elements.
GFF_CHECKS = [
    ('utc', 'Appearance_Type', 'appearance', None),
    ('utc', 'PortraitId', 'portraits', None),
    ('utc', 'SoundSetFile', 'soundset', 65535),
    ('utc', 'BodyBag', 'bodybag', None),
    ('utc', 'FactionID', 'repute', None),
    ('utc', 'Race', 'racialtypes', None),
    ('utc', 'Gender', 'gender', None),
    ('utc', 'WalkRate', 'creaturespeed', None),
    ('utc', 'PerceptionRange', 'ranges', None),
    ('utc', 'SubraceIndex', 'subrace', None),
    ('utc', 'ClassList[]/Class', 'classes', None),
    ('utc', 'FeatList[]/Feat', 'feat', None),
    ('utc', 'ClassList[]/KnownList0[]/Spell', 'spells', None),
    ('utc', 'SpecAbilityList[]/Spell', 'spells', None),
    ('utp', 'Appearance', 'placeables', None),
    ('utp', 'BodyBag', 'bodybag', None),
    ('utp', 'Faction', 'repute', 4294967295),
    ('utp', 'TrapType', 'traps', None),
    ('utd', 'GenericType', 'genericdoors', None),
    ('utd', 'Appearance', 'doortypes', None),
    ('utd', 'Faction', 'repute', None),
    ('utd', 'TrapType', 'traps', None),
    ('utd', 'LoadScreenID', 'loadscreens', None),
    ('utd', 'PortraitId', 'portraits', None),
    ('uti', 'BaseItem', 'baseitems', None),
    ('uti', 'PropertiesList[]/PropertyName', 'itempropdef', None),
    ('uti', 'PropertiesList[]/CostTable', 'iprp_costtable', None),
    ('uti', 'PropertiesList[]/Param1', 'iprp_paramtable', 255),
    ('uti', 'PropertiesList[]/UpgradeType', 'upgradetypes', 255),
    ('utt', 'TrapType', 'traps', None),
    ('utt', 'Cursor', 'cursors', None),
    ('utt', 'Faction', 'repute', None),
    ('utt', 'LoadScreenID', 'loadscreens', None),
    ('utt', 'PortraitId', 'portraits', None),
    ('ute', 'DifficultyIndex', 'encdifficulty', None),
    ('ute', 'CreatureList[]/Appearance', 'appearance', None),
    ('ute', 'Faction', 'repute', None),
    ('utw', 'Appearance', 'waypoint', None),
    ('are', 'CameraStyle', 'camerastyle', None),
    ('are', 'LoadScreenID', 'loadscreens', None),
    ('are', 'PlayerVsPlayer', 'pvpsettings', None),
    ('are', 'Rooms[]/EnvAudio', 'soundeax', None),
    ('git', 'AreaProperties/AmbientSndDay', 'ambientsound', None),
    ('git', 'AreaProperties/AmbientSndNight', 'ambientsound', None),
    ('git', 'AreaProperties/MusicDay', 'ambientmusic', None),
    ('git', 'AreaProperties/MusicNight', 'ambientmusic', None),
    ('git', 'AreaProperties/MusicBattle', 'ambientmusic', None),
    ('git', 'AreaProperties/EnvAudio', 'soundeax', None),
    ('git', 'WaypointList[]/Appearance', 'waypoint', None),
    ('dlg', 'EntryList[]/AnimList[]/Animation', 'dialoganimations', 'dialog'),
    ('dlg', 'ReplyList[]/AnimList[]/Animation', 'dialoganimations', 'dialog'),
]

# nwscript.nss constant groups that name 2DA rows: (prefix, table, column, key).
# key 'index': the constant's value is the row index; 'label': it is the row label.
# A constant counts as matched when the row it points at has a label/constant cell sharing a word
# with the constant name (after the prefix).
CONST_CHECKS = [
    ('BASE_ITEM_', 'baseitems', ('label',), 'index'),
    ('FEAT_', 'feat', ('constant', 'label'), 'index'),
    ('FORCE_POWER_', 'spells', ('label',), 'index'),
    ('SKILL_', 'skills', ('constant',), 'index'),
    ('CLASS_TYPE_', 'classes', ('label', 'constant'), 'index'),
    ('RACIAL_TYPE_', 'racialtypes', ('constant',), 'index'),
    ('GENDER_', 'gender', ('constant',), 'index'),
    ('STANDARD_FACTION_', 'repute', ('label',), 'index'),
    ('POISON_', 'poison', ('label',), 'index'),
    ('TRAP_BASE_TYPE_', 'traps', ('label',), 'index'),
    ('VFX_', 'visualeffects', ('label',), 'label'),
    ('SHIELD_', 'forceshields', ('label',), 'index'),
    ('VIDEO_EFFECT_', 'videoeffects', ('label',), 'index'),
    ('PLANET_', 'planetary', ('label',), 'index'),
    ('ENCOUNTER_DIFFICULTY_', 'encdifficulty', ('label',), 'index'),
    ('CREATURE_SIZE_', 'creaturesize', ('label',), 'index'),
    ('ITEM_PROPERTY_', 'itemprops', ('label',), 'index'),
    ('DISGUISE_TYPE_', 'appearance', ('label', 'race', 'modela'), 'index'),
    ('NPC_', 'npc', ('tag',), 'index'),
    ('POLYMORPH_TYPE_', 'polymorph', ('name',), 'index'),
    ('AOE_', 'vfx_persistent', ('label',), 'index'),
]
# Constants that share a prefix with a group but belong elsewhere.
CONST_EXCLUDE = ('NPC_AISTYLE_', 'NPC_PLAYER')


def build_resource_index(g):
    """resref -> set of types over every container in the install plus the loose folders."""
    idx = defaultdict(set)
    for e in g.every_entry():
        idx[e.resref].add(e.ext)
    for sub in LOOSE_DIRS:
        root = os.path.join(g.dir, sub)
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for n in files:
                stem, dot, x = n.rpartition('.')
                if dot:
                    idx[stem.lower()].add(x.lower())
    return idx


def module_names(g):
    out = set()
    for n in os.listdir(os.path.join(g.dir, 'modules')):
        stem, _, x = n.lower().rpartition('.')
        if x in ('rim', 'mod') and not stem.endswith('_s'):
            out.add(stem)
    return out


def classify(values):
    ne = [v for v in values if v != '']
    if not ne:
        return 'empty'
    if all(INT_RE.match(v) for v in ne):
        return 'int'
    if all(HEX_RE.match(v) for v in ne):
        return 'hex'
    if all(INT_RE.match(v) or HEX_RE.match(v) for v in ne):
        return 'int/hex'
    if all(FLOAT_RE.match(v) for v in ne):
        return 'float'
    return 'string'


def profile_column(name, values, tlk, residx, table_names):
    ne = [v for v in values if v != '']
    distinct = Counter(ne)
    kind = classify(values)
    p = {
        'name': name,
        'nonempty': len(ne),
        'distinct': len(distinct),
        'kind': kind,
        'samples': [v for v, _ in distinct.most_common(6)],
    }
    if kind == 'int':
        ints = [int(v) for v in ne]
        p['min'] = min(ints)
        p['max'] = max(ints)
        if TEXTY_RE.search(name.lower()):
            ok = sum(1 for v in ints if v >= 0 and tlk.text(v))
            p['strref_rate'] = round(ok / len(ints), 3)
            p['strref_examples'] = [(v, (tlk.text(int(v)) or '')[:50]) for v in list(distinct)[:2]]
    elif kind == 'string':
        keys = [v.lower() for v in distinct]
        cand = [k for k in keys if RESREF_RE.match(k)]
        if cand:
            hits = Counter()
            for k in cand:
                for t in residx.get(k, ()):
                    hits[t] += 1
            best = [(t, round(n / len(keys), 3)) for t, n in hits.most_common(4) if n / len(keys) >= 0.2]
            if best:
                p['resref_hits'] = best
        t2 = sum(1 for k in keys if k in table_names)
        if t2 and t2 / len(keys) >= 0.2:
            p['names_2da'] = round(t2 / len(keys), 3)
    return p


def column_values(t, col):
    if col == '#label':
        return list(t.row_labels)
    return t.column(col)


def run_check(chk, tables, tlk, residx, modules):
    table, col, kind, arg = chk
    t = tables.get(table)
    if t is None or kind is None:
        return None
    if col != '#label' and not t.has(col):
        return {'check': chk, 'error': 'no such column'}
    vals = [v for v in column_values(t, col) if v not in ('', '-1')]
    distinct = sorted(set(v.lower() for v in vals))
    miss = []
    for v in distinct:
        if kind == 'res':
            types, pat = arg
            ok = bool(residx.get(pat.format(v).lower(), set()) & set(types))
        elif kind == 'row':
            tt = tables.get(arg)
            ok = INT_RE.match(v) is not None and tt is not None and 0 <= int(v) < len(tt.rows)
        elif kind == 'label':
            ok = v in {x.lower() for x in tables[arg].row_labels}
        elif kind == 'match':
            tt, c = arg
            ok = v in {x.lower() for x in tables[tt].column(c)}
        elif kind == 'col':
            tt, pat = arg
            ok = tables[tt].has(pat.format(v))
        elif kind == 'colnum':
            ok = any(c.lower().startswith(v + '_') for c in tables[arg].columns)
        elif kind == 'rowlist':
            n = len(tables[arg].rows)
            ok = all(INT_RE.match(p) and 0 <= int(p) < n for p in v.split('_'))
        elif kind == 'strref':
            ok = INT_RE.match(v) is not None and bool(tlk.text(int(v)))
        elif kind == '2da':
            ok = arg.format(v).lower() in tables
        elif kind == 'module':
            ok = v in modules
        else:
            return None
        if not ok:
            miss.append(v)
    return {'check': chk, 'n': len(distinct), 'hits': len(distinct) - len(miss), 'misses': miss[:12]}


def describe_check(chk):
    table, col, kind, arg = chk
    if kind == 'res':
        types, pat = arg
        tgt = '/'.join(types) + ('' if pat == '{}' else f' as "{pat}"')
    elif kind in ('match', 'col'):
        tgt = f'{arg[0]}.{arg[1]}'
    else:
        tgt = arg or ''
    return f'{table}.{col} -> {kind} {tgt}'.rstrip()


# --- GFF field checks -------------------------------------------------------------------------

def _gff_values(struct, path):
    """Values of an integer field at path ('A/B[]/C') in a gffpy Struct."""
    head, _, rest = path.partition('/')
    is_list = head.endswith('[]')
    label = head[:-2] if is_list else head
    v = struct.get(label)
    if v is None:
        return []
    if not rest:
        return [v] if isinstance(v, int) else []
    items = v if is_list else [v]
    out = []
    for it in items:
        if hasattr(it, 'fields'):
            out.extend(_gff_values(it, rest))
    return out


def run_gff_checks(g, tables):
    try:
        import gffpy
    except ImportError:
        return None, 'gffpy.py not found'
    by_ext = defaultdict(list)
    for chk in GFF_CHECKS:
        by_ext[chk[0]].append(chk)
    results = []
    files = {}
    for ext, chks in by_ext.items():
        counts = [Counter() for _ in chks]
        nfiles = 0
        for e in g.entries(ext):
            try:
                root = gffpy.read(kres.read_entry(e))
            except Exception:
                continue
            nfiles += 1
            for i, (_x, path, _t, _s) in enumerate(chks):
                for v in _gff_values(root, path):
                    counts[i][v] += 1
        files[ext] = nfiles
        for (x, path, table, sentinel), c in zip(chks, counts):
            t = tables[table]
            n = len(t.rows)
            uses = sum(c.values())
            bad = Counter()
            none = 0
            for v, k in c.items():
                if sentinel == 'dialog':
                    # Dialog animations: 10000 + row of dialoganimations; smaller numbers are
                    # other animation ids (camera/stunt), counted as "none" here.
                    if v < 10000:
                        none += k
                        continue
                    v -= 10000
                    if 0 <= v < n and not t.rows[v][0]:
                        bad[f'{v + 10000}(unnamed row)'] += k
                        continue
                elif v == sentinel:
                    none += k
                    continue
                if not (0 <= v < n):
                    bad[v] += k
            results.append({'check': (x, path, table), 'uses': uses, 'none': none,
                            'distinct': len(c), 'bad_uses': sum(bad.values()),
                            'bad': sorted(bad.items(), key=lambda kv: -kv[1])[:8],
                            'max': max(c) if c else None, 'rows': n})
    return results, files


# --- nwscript.nss constant checks -------------------------------------------------------------

def _words(s):
    return {w for w in re.split(r'[^a-z0-9]+', s.lower()) if len(w) > 1}


def _squash(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def run_const_checks(g, tables):
    data = g.get('nwscript', 'nss')
    if data is None:
        return None
    consts = {}
    for m in re.finditer(r'^\s*int\s+([A-Z][A-Z0-9_]*)\s*=\s*(-?\d+)\s*;', data.decode('latin-1'), re.M):
        consts[m.group(1)] = int(m.group(2))
    out = []
    for prefix, table, cols, key in CONST_CHECKS:
        t = tables[table]
        group = {k: v for k, v in consts.items()
                 if k.startswith(prefix) and not k.startswith(CONST_EXCLUDE)}
        if key == 'label':
            rows = {lab: i for i, lab in enumerate(t.row_labels)}
        matched, out_of_range, mismatched = 0, [], []
        for name, v in sorted(group.items(), key=lambda kv: kv[1]):
            r = rows.get(str(v)) if key == 'label' else (v if 0 <= v < len(t.rows) else None)
            if r is None:
                out_of_range.append(f'{name}={v}')
                continue
            cells = [t.rows[r][t.col_index(c)] for c in cols]
            short = name[len(prefix):]
            if any(name.lower() == c.lower() or _words(short) & _words(c)
                   or _squash(short) == _squash(c) for c in cells):
                matched += 1
            else:
                mismatched.append(f'{name}={v}:{cells[0] or "****"}')
        out.append({'prefix': prefix, 'table': table, 'key': key, 'constants': len(group),
                    'matched': matched, 'out_of_range': out_of_range[:8],
                    'n_out_of_range': len(out_of_range), 'mismatched': mismatched[:8],
                    'n_mismatched': len(mismatched)})
    return out


# --- walkmesh materials ----------------------------------------------------------------------

def run_bwm_check(g, tables):
    """Face materials of every WOK/PWK/DWK against surfacemat.2da rows. Assumes the BWM V1.0
    header keeps the face count at byte 80 and the material array offset at byte 88."""
    import struct
    n = len(tables['surfacemat'].rows)
    out = {}
    for ext in ('wok', 'pwk', 'dwk'):
        c = Counter()
        files = 0
        for e in g.entries(ext):
            d = kres.read_entry(e)
            if d[:8] != b'BWM V1.0' or len(d) < 92:
                continue
            fc, _fo, mo = struct.unpack_from('<3I', d, 80)
            if mo + 4 * fc > len(d):
                continue
            files += 1
            c.update(struct.unpack_from(f'<{fc}I', d, mo))
        out[ext] = {'files': files, 'faces': sum(c.values()),
                    'out_of_range': sum(k for m, k in c.items() if m >= n),
                    'materials': sorted(c.items())}
    return out


# --- main --------------------------------------------------------------------------------------

def describe_container(g, path):
    return os.path.relpath(path, g.dir).replace('\\', '/')


def _diff_summary(a, b):
    parts = []
    if a.columns != b.columns:
        extra = [c for c in a.columns if c not in b.columns]
        gone = [c for c in b.columns if c not in a.columns]
        parts.append(f'columns {len(a.columns)} vs {len(b.columns)} (+{extra} -{gone})')
    if len(a.rows) != len(b.rows):
        parts.append(f'rows {len(a.rows)} vs {len(b.rows)}')
    common = [c for c in a.columns if c in b.columns]
    n = 0
    cells = []
    for r in range(min(len(a.rows), len(b.rows))):
        for c in common:
            x, y = a.get(r, c), b.get(r, c)
            if x != y:
                n += 1
                if len(cells) < 4:
                    cells.append(f'row {r} {c}: {y!r}->{x!r}')
    parts.append(f'{n} common cells differ' + (f' ({"; ".join(cells)})' if cells else ''))
    return ', '.join(parts)


def main(argv):
    out_dir = argv[argv.index('--out') + 1] if '--out' in argv else DEFAULT_OUT
    os.makedirs(out_dir, exist_ok=True)
    g = kres.Game()
    tlk = tlkpy.load(g.dir)
    entries = g.every_entry('2da')
    by_name = defaultdict(list)
    failures = []
    for e in entries:
        data = kres.read_entry(e)
        try:
            t = twodapy.parse(data)
        except Exception as ex:  # report and continue: a probe sees everything
            failures.append((e, str(ex)))
            t = None
        by_name[e.resref].append((e, data, t))
    table_names = set(by_name)
    residx = build_resource_index(g)
    modules = module_names(g)

    chosen = {}
    dup_report = []
    for name, copies in sorted(by_name.items()):
        good = [c for c in copies if c[2] is not None]
        if not good:
            continue
        pick = next((c for c in good if 'patch.erf' in c[0].container.lower()), None)
        pick = pick or next((c for c in good if c[0].container.lower().endswith('.bif')), good[0])
        chosen[name] = pick
        if len(copies) > 1:
            notes = []
            for c in copies:
                if c is pick:
                    continue
                where = describe_container(g, c[0].container)
                if c[1] == pick[1]:
                    notes.append(f'{where}: byte-identical')
                elif c[2] is None:
                    notes.append(f'{where}: does not parse')
                elif c[2].columns == pick[2].columns and c[2].rows == pick[2].rows \
                        and c[2].row_labels == pick[2].row_labels:
                    sep = 'NUL' if c[2].label_sep == '\0' else 'tab'
                    notes.append(f'{where}: same cells, labels end with {sep}')
                else:
                    notes.append(f'{where}: DIFFERENT content ({_diff_summary(pick[2], c[2])})')
            dup_report.append((name, describe_container(g, pick[0].container), notes))

    tables = {n: c[2] for n, c in chosen.items()}
    inv = []
    for name, (e, data, t) in sorted(chosen.items()):
        cols = [profile_column(cn, [r[i] for r in t.rows], tlk, residx, table_names)
                for i, cn in enumerate(t.columns)]
        labels_seq = all(rl == str(i) for i, rl in enumerate(t.row_labels))
        inv.append({
            'name': name,
            'copies': [{'container': describe_container(g, c[0].container), 'size': c[0].size,
                        'sha1': hashlib.sha1(c[1]).hexdigest()[:12]} for c in by_name[name]],
            'profiled_copy': describe_container(g, e.container),
            'rows': len(t.rows),
            'columns': len(t.columns),
            'row_labels_sequential': labels_seq,
            'row_labels': [] if labels_seq else t.row_labels,
            'cols': cols,
        })
    checks = [r for r in (run_check(c, tables, tlk, residx, modules) for c in CHECKS) if r]
    gff_checks, gff_files = (None, None) if '--no-gff' in argv else run_gff_checks(g, tables)
    const_checks = run_const_checks(g, tables)
    bwm_check = run_bwm_check(g, tables)

    with open(os.path.join(out_dir, '2da-inventory.json'), 'w', encoding='utf-8') as f:
        json.dump({'entries': len(entries), 'tables': len(inv),
                   'failures': [(f'{e.resref} {e.container}', m) for e, m in failures],
                   'duplicates': dup_report, 'tables_detail': inv, 'checks': checks,
                   'gff_checks': gff_checks, 'gff_files': gff_files,
                   'const_checks': const_checks, 'bwm_check': bwm_check}, f, indent=1)
    with open(os.path.join(out_dir, '2da-inventory.txt'), 'w', encoding='utf-8') as f:
        for t in inv:
            where = ', '.join(sorted(set(c['container'] for c in t['copies'])))
            f.write(f"== {t['name']}  rows={t['rows']} cols={t['columns']}  in: {where}\n")
            if not t['row_labels_sequential']:
                f.write(f"   row labels not 0..n-1: {t['row_labels'][:24]}\n")
            for c in t['cols']:
                extra = ''
                if c['kind'] == 'int':
                    extra = f" [{c['min']}..{c['max']}]"
                    if 'strref_rate' in c:
                        extra += f" tlk={c['strref_rate']} e.g. " + ' | '.join(
                            f'{v}="{s}"' for v, s in c['strref_examples'])
                if 'resref_hits' in c:
                    extra += ' res=' + ','.join(f'{x}:{r}' for x, r in c['resref_hits'])
                if 'names_2da' in c:
                    extra += f" 2da={c['names_2da']}"
                samp = ', '.join(c['samples'][:6])
                f.write(f"   {c['name']:<22} {c['kind']:<7} {c['nonempty']:>4}/{t['rows']:<4} "
                        f"d={c['distinct']:<4}{extra}  :: {samp}\n".replace('\r', ' '))
            f.write('\n')

    print(f'2DA entries read: {len(entries)} (every copy: BIFs, RIMs, patch.erf, Override, saves)')
    print(f'distinct tables: {len(inv)}; rows total {sum(t["rows"] for t in inv)}')
    print(f'parse failures: {len(failures)}')
    for e, m in failures:
        print(f'  {e.resref}.2da in {describe_container(g, e.container)}: {m}')
    seps = Counter((describe_container(g, c[0].container), c[2].label_sep)
                   for cs in by_name.values() for c in cs if c[2] is not None)
    print('copies by container and label terminator:',
          ', '.join(f'{k[0]} {"NUL" if k[1] == chr(0) else "tab"}: {n}' for k, n in sorted(seps.items())))
    print(f'tables with more than one copy: {len(dup_report)}')
    kinds = Counter()
    for name, where, notes in dup_report:
        for n in notes:
            kinds[n.split(': ', 1)[1].split(' (')[0]] += 1
        if any('DIFFERENT' in n or 'NUL' in n for n in notes):
            print(f'  {name} (profiled: {where}):')
            for n in notes:
                print(f'    {n}')
    print('copy comparisons:', dict(kinds))
    print('cross-reference checks (distinct values that resolve / distinct values):')
    for r in checks:
        if 'error' in r:
            print(f'  {describe_check(r["check"])}: {r["error"]}')
            continue
        miss = f"  misses: {r['misses']}" if r['misses'] else ''
        print(f'  {describe_check(r["check"])}: {r["hits"]}/{r["n"]}{miss}')
    if gff_checks is None:
        print(f'GFF field checks skipped: {gff_files}')
    else:
        print('GFF field checks (uses in range / uses; "none" = sentinel; files read per type: '
              + ', '.join(f'{k} {v}' for k, v in gff_files.items()) + '):')
        for r in gff_checks:
            x, path, table = r['check']
            bad = f"  out of range: {r['bad']}" if r['bad'] else ''
            none = f" (+{r['none']} none)" if r['none'] else ''
            print(f'  {x}.{path} -> {table} ({r["rows"]} rows): '
                  f'{r["uses"] - r["none"] - r["bad_uses"]}/{r["uses"] - r["none"]}{none}, '
                  f'max {r["max"]}{bad}')
    a, b = tables['itempropdef'], tables['itemprops']
    same = sum(1 for x, y in zip(a.column('name'), b.column('stringref')) if x == y)
    print(f'itemprops.stringref == itempropdef.name on the same row: {same}/{len(a.rows)}')
    sm = tables['surfacemat']
    print('walkmesh face materials -> surfacemat rows:')
    for ext, r in bwm_check.items():
        used = ', '.join(f'{m} {sm.rows[m][0] if m < len(sm.rows) else "?"}:{k}' for m, k in r['materials'])
        print(f"  {ext}: {r['files']} files, {r['faces']} faces, {r['out_of_range']} out of range; {used}")
    bif_only = sorted(n for n, cs in by_name.items()
                      if not any('global.rim' in c[0].container.lower() for c in cs))
    print(f'tables not in rims/global.rim ({len(bif_only)}): {" ".join(bif_only)}')
    exe = os.path.normpath(os.path.join(HERE, '..', '..', 're', 'bin', 'swkotor_unpacked.exe'))
    if os.path.isfile(exe):
        with open(exe, 'rb') as f:
            strs = {m.group().decode('latin-1').lower() for m in re.finditer(rb'[ -~]{3,}', f.read())}
        named = sorted(n for n in by_name if n in strs)
        print(f'table names found as strings in re/bin/swkotor_unpacked.exe ({len(named)}): '
              f'{" ".join(named)}')
        print(f'not found ({len(by_name) - len(named)}): '
              f'{" ".join(sorted(n for n in by_name if n not in strs))}')
    if const_checks is not None:
        print('nwscript.nss constants (matched / constants; matched = the row it names carries '
              'the same name):')
        for r in const_checks:
            extra = ''
            if r['n_out_of_range']:
                extra += f"  no row ({r['n_out_of_range']}): {r['out_of_range']}"
            if r['n_mismatched']:
                extra += f"  other name ({r['n_mismatched']}): {r['mismatched']}"
            print(f"  {r['prefix']}* -> {r['table']} by {r['key']}: "
                  f"{r['matched']}/{r['constants']}{extra}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
