"""Generate another_game_framework's KOTOR container templates from the install.

    python kotor/tools/py/agf_containers.py [--agf DIR]

Writes `apps/kotor/src/containers.ts` in the framework repo (default
G:/Dev/another_game_framework): the fixed items of every container template (UTP) a module places,
as inventory definitions. A module's GIT only names a template, so the template's ItemList is what
every container placed from it holds; each item's StackSize is its count.

Items are matched to the framework's seeded items (apps/kotor/src/items.ts, upgrades.ts) by name,
with OVERRIDES settling names several items share. Items with no match (Pazaak cards, which go to
the side deck rather than the inventory) are left out and listed. A template id is its resref, prefixed with the module when
copies in different modules hold different items.

Placed containers and their loot rolls aren't written yet: they come with the framework's world
placement. TRES maps each k_plc_tres* script (OnOpen or OnHeartbeat) to its loot table for then;
the report counts them.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

import gff
import kres
import tlkpy

DEFAULT_AGF = r'G:\Dev\another_game_framework'

TRES = {
    'k_plc_tresciv': 'civilian',
    'k_plc_tresmillow': 'military_low',
    'k_plc_tresmilmid': 'military_mid',
    'k_plc_tresmilhig': 'military_high',
    'k_plc_trescorlow': 'corpse_low',
    'k_plc_trescormid': 'corpse_mid',
    'k_plc_trescorhig': 'corpse_high',
    'k_plc_tresshalow': 'shadowlands_low',
    'k_plc_tresshamid': 'shadowlands_mid',
    'k_plc_tresshahig': 'shadowlands_high',
    'k_plc_tresdrdlow': 'droid_low',
    'k_plc_tresdrdmid': 'droid_mid',
    'k_plc_tresdrdhig': 'droid_high',
    'k_plc_tresrakat': 'rakatan',
    'k_plc_tressndppl': 'sand_people',
}

# Templates whose name matches several framework items, settled by price, properties or content,
# keyed by resref or, where a resref is a different item in each module, by module/resref. Robes,
# which differ only in texture, are numbered in resref order (robe_overrides).
OVERRIDES = {
    'g_w_vbroswrd01': 'vibrosword',
    'k37_itm_freednf2': 'vibrosword_3',
    'g_w_hldoblstr03': 'sith_assassin_pistol',
    'g_i_drdutldev007': 'advanced_flame_thrower',
    'g_i_belt010': 'stealth_field_generator',
    # Story datapads, all named "Datapad"
    'tar_m08aa/g_i_datapad002': 'calo_nord_datapad',
    'kor37_datapad01': 'veren_gal_datapad',
    'kor37_datapad02': 'sith_student_datapad',
    'kor39_itm_datapd': 'sith_test_datapad',
    'unk44_data': 'sequencer_datapad',
    'manm27aa/w_sdatapad': 'dark_jedi_master_datapad',
    # Rakghoul serum: the plot copy, and the two Zelka sells at different prices
    'ptar_rakghoulser': 'rakghoul_serum',
    'ptar_rakghoul001': 'rakghoul_serum_2',
    'ptar_rakghoul002': 'rakghoul_serum_3',
}

ITEM_ROW = re.compile(r'\{ id: "([a-z0-9_]+)",(?: itemTypeId: "[a-z0-9_]+",)? '
                      r'name: ("(?:[^"\\]|\\.)*"), description: ')
PRICE_ROW = re.compile(r'\{ itemDefinitionId: "([a-z0-9_]+)", basePrice: (\d+) \}')


def item_value(u):
    """An item template's value, as the game computes it (`CSWSItem::GetCost`): 0 for a plot item,
    else its AddCost, at least 1. The template's Cost is a stale editor value the game never reads
    (party-items-saves.md 5.1)."""
    return 0 if u.get('Plot') else max(1, u.get('AddCost') or 0)


def txt(v):
    if isinstance(v, bytes):
        return v.decode('latin-1').lower()
    return '' if v is None else str(v)


def framework_items(agf):
    """name (lower case) -> ids, from the seeded item definitions, and id -> price, from the
    tradable items; an item that isn't tradable, as a plot item isn't, is worth 0."""
    src_dir = os.path.join(agf, 'apps', 'kotor', 'src')
    by_name, prices = defaultdict(list), defaultdict(int)
    for f in ('items.ts', 'upgrades.ts'):
        src = open(os.path.join(src_dir, f), encoding='utf-8').read()
        for item_id, name in ITEM_ROW.findall(src):
            name = json.loads(name).lower()
            if item_id not in by_name[name]:
                by_name[name].append(item_id)
    src = open(os.path.join(src_dir, 'tradableItems.ts'), encoding='utf-8').read()
    for item_id, price in PRICE_ROW.findall(src):
        prices[item_id] = int(price)
    return by_name, prices


class Install:
    def __init__(self):
        self.game = kres.Game()
        self.tlk = tlkpy.load(self.game.dir)
        self.chitin = {(e.resref, e.ext): e for e in kres.read_key(self.game.dir)
                       if e.ext in ('utp', 'uti')}

    def name(self, s, label):
        ls = s.get(label)
        if ls is None:
            return ''
        if ls.strref >= 0:
            return self.tlk.text(ls.strref) or ''
        return ls.strings[0][1].decode('cp1252') if ls.strings else ''

    def modules(self):
        """module -> its RIM/MOD files (the module and its _s companion)."""
        mods = defaultdict(list)
        d = os.path.join(self.game.dir, 'modules')
        for n in sorted(os.listdir(d)):
            low = n.lower()
            if low.endswith(('.rim', '.mod')):
                stem = low.rsplit('.', 1)[0]
                mods[stem[:-2] if stem.endswith('_s') else stem].append(os.path.join(d, n))
        return mods


def robe_overrides(install, by_name):
    """Same-name robes differ only in texture: number each name's templates in resref order."""
    refs = defaultdict(list)
    for (ref, ext), e in sorted(install.chitin.items()):
        if ext == 'uti' and ref.startswith('g_a_') and 'robe' in ref:
            name = install.name(gff.read(kres.read_entry(e)).root, 'LocalizedName').lower()
            if len(by_name.get(name, [])) > 1:
                refs[name].append(ref)
    out = {}
    for name, rs in refs.items():
        base = by_name[name][0]
        for k, ref in enumerate(rs[:len(by_name[name])]):
            out[ref] = base if k == 0 else f'{base}_{k + 1}'
    return out


def placed_templates(install):
    """(module, resref) -> template, and placements per (module, resref), for every placed
    placeable with an inventory. A module's own UTP/UTI wins over chitin's."""
    templates, placed = {}, Counter()
    for mod, files in sorted(install.modules().items()):
        entries = {}
        for f in files:
            for e in kres.read_container(f):
                entries[(e.resref, e.ext)] = e

        def find(ref, ext):
            return entries.get((ref, ext)) or install.chitin.get((ref, ext))

        for git in [e for k, e in entries.items() if k[1] == 'git']:
            for p in gff.read(kres.read_entry(git)).root.get('Placeable List') or []:
                ref = txt(p.get('TemplateResRef'))
                s = gff.read(kres.read_entry(find(ref, 'utp'))).root
                if not s.get('HasInventory'):
                    continue
                placed[(mod, ref)] += 1
                if (mod, ref) in templates:
                    continue
                scripts = [txt(f.value) for f in s.fields if f.label.startswith('On') and f.value]
                loot = [TRES[x] for x in scripts if x in TRES]
                items = []
                for it in s.get('ItemList') or []:
                    iref = txt(it.get('InventoryRes'))
                    u = gff.read(kres.read_entry(find(iref, 'uti'))).root
                    value = item_value(u)
                    items.append((iref, install.name(u, 'LocalizedName'), u.get('StackSize') or 1,
                                  value))
                templates[(mod, ref)] = {'loot': loot[0] if loot else None, 'items': items}
    return templates, placed


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--agf', default=DEFAULT_AGF, help='the framework repo')
    args = ap.parse_args(argv)

    install = Install()
    by_name, prices = framework_items(args.agf)
    overrides = {**robe_overrides(install, by_name), **OVERRIDES}
    templates, placed = placed_templates(install)

    unseeded, price_mismatches, resolved = Counter(), set(), {}
    for key, t in templates.items():
        stacks = Counter()
        for iref, name, count, value in t['items']:
            override = overrides.get(f'{key[0]}/{iref}') or overrides.get(iref)
            ids = [override] if override else by_name.get(name.lower(), [])
            if len(ids) > 1:
                raise SystemExit(f'{iref} ({name}) matches {ids}: add it to OVERRIDES')
            if not ids:
                unseeded[(iref, name)] += placed[key]
                continue
            if ids[0] != 'credits' and prices[ids[0]] != value:
                price_mismatches.add((iref, name, value, ids[0], prices[ids[0]]))
            stacks[ids[0]] += count
        resolved[key] = stacks

    # One id per resref when every module's copy holds the same items, else one per module.
    by_ref = defaultdict(list)
    for key in templates:
        if resolved[key]:
            by_ref[key[1]].append(key)
    rows = []
    for ref, keys in sorted(by_ref.items()):
        if len({tuple(sorted(resolved[k].items())) for k in keys}) == 1:
            rows.append((ref, keys[0]))
        else:
            rows.extend((f'{k[0]}_{ref}', k) for k in sorted(keys))

    q = lambda s: json.dumps(s, ensure_ascii=False)  # noqa: E731
    out = ['import type { InventoryDefinitionStack } from "@agf/core";', '',
           '/**',
           " * KOTOR's container templates (UTP) as inventory definitions: the fixed items every",
           ' * container placed from one starts with. Ids are the template resrefs, prefixed with the',
           ' * module where its copies differ. Placed containers come with the world.',
           ' *',
           " * Generated from the install by the RE repo's `kotor/tools/py/agf_containers.py`.",
           ' */',
           'export const KOTOR_CONTAINER_ITEMS: InventoryDefinitionStack[] = [']
    for template_id, key in rows:
        for item, count in sorted(resolved[key].items()):
            out.append(f'  {{ inventoryDefinitionId: {q(template_id)}, itemDefinitionId: {q(item)},'
                       f' itemCount: {count} }},')
    out += ['];', '']
    path = os.path.join(args.agf, 'apps', 'kotor', 'src', 'containers.ts')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(out))

    print(f'wrote {path}: {len(rows)} templates, {sum(len(resolved[k]) for _, k in rows)} stacks')
    print(f'placed containers: {sum(placed.values())}, from a template with items:'
          f' {sum(placed[k] for k in templates if resolved[k])}')
    rolls = [k for k in templates if templates[k]['loot']]
    print(f'templates rolling a loot table: {len({k[1] for k in rolls})}'
          f' ({sum(placed[k] for k in rolls)} placements)')
    print(f'items left out: {len(unseeded)} templates, {sum(unseeded.values())} entries')
    for (ref, name), n in unseeded.most_common():
        print(f'    {ref} ({name}) x{n}')
    print(f'price mismatches: {len(price_mismatches)}')
    for m in sorted(price_mismatches):
        print('   ', m)


if __name__ == '__main__':
    main(sys.argv[1:])
