"""Generate another_game_framework's KOTOR stores from the install.

    python kotor/tools/py/agf_stores.py [--agf DIR]

Writes `apps/kotor/src/stores.ts` in the framework repo (default G:/Dev/another_game_framework):
every store template (UTM) in a module, with its MarkUp, MarkDown and BuySellFlag, and its stock.
A store's id is its tag, which scripts find it by (`GetObjectByTag`) and which no two templates
share, and its stock lives in the inventory `<id>:stock`. A stock entry names an item template; entries for one item add up their
StackSize, and an Infinite entry makes it an item the store never runs out of, written without a
count.

Items are matched to the framework's seeded items as agf_containers.py matches them. Items with no
match (Pazaak cards, which go to the side deck rather than the inventory, and plot items left out of
the item data) are left out and listed.
"""
import argparse
import json
import os
import sys
from collections import Counter

import gff
import kres
from agf_containers import (DEFAULT_AGF, OVERRIDES, Install, framework_items, item_value,
                            robe_overrides, txt)

# BuySellFlag: 1 the player can only buy, 2 only sell, 3 both (party-items-saves.md 5.8).
TRADES = {1: 'sellsOnly', 2: 'buysOnly', 3: 'sellsAndBuys'}


def module_stores(install):
    """tag -> (module, store root, the module's resources), for every UTM in a module."""
    stores = {}
    for mod, files in sorted(install.modules().items()):
        entries = {}
        for f in files:
            for e in kres.read_container(f):
                entries[(e.resref, e.ext)] = e
        for (ref, ext), e in sorted(entries.items()):
            if ext != 'utm':
                continue
            root = gff.read(kres.read_entry(e)).root
            tag = txt(root.get('Tag'))
            if tag in stores:
                raise SystemExit(f'store tag {tag} is in {stores[tag][0]} and {mod} ({ref})')
            stores[tag] = (mod, root, entries)
    return stores


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--agf', default=DEFAULT_AGF, help='the framework repo')
    args = ap.parse_args(argv)

    install = Install()
    by_name, prices = framework_items(args.agf)
    overrides = {**robe_overrides(install, by_name), **OVERRIDES}
    stores = module_stores(install)

    unseeded, price_mismatches, rows, stock = Counter(), set(), [], {}
    for ref, (mod, root, entries) in sorted(stores.items()):
        flag = root.get('BuySellFlag')
        if flag not in TRADES:
            raise SystemExit(f'store {ref} has BuySellFlag {flag}')
        rows.append((ref, root.get('MarkUp'), root.get('MarkDown'), TRADES[flag]))
        counts, infinite = Counter(), set()
        for it in root.get('ItemList') or []:
            iref = txt(it.get('InventoryRes'))
            u = gff.read(kres.read_entry(entries.get((iref, 'uti'))
                                         or install.chitin.get((iref, 'uti')))).root
            name = install.name(u, 'LocalizedName')
            override = overrides.get(f'{mod}/{iref}') or overrides.get(iref)
            ids = [override] if override else by_name.get(name.lower(), [])
            if len(ids) > 1:
                raise SystemExit(f'{iref} ({name}) matches {ids}: add it to OVERRIDES')
            if not ids:
                unseeded[(iref, name)] += 1
                continue
            value = item_value(u)
            if prices[ids[0]] != value:
                price_mismatches.add((iref, name, value, ids[0], prices[ids[0]]))
            if it.get('Infinite'):
                infinite.add(ids[0])
            else:
                counts[ids[0]] += u.get('StackSize') or 1
        stock[ref] = (counts, infinite)

    q = lambda s: json.dumps(s, ensure_ascii=False)  # noqa: E731
    out = ['import type { Store, StoreStockItem } from "@agf/core";', '',
           '/**',
           " * KOTOR's stores (UTM), each placed in one module or opened by its scripts: what they charge",
           " * and pay as a percentage of an item's value, and which ways they trade. Some merchants have",
           " * several, such as Zelka's six with different stock and markups; scripts pick which opens.",
           ' *',
           " * Generated from the install by the RE repo's `kotor/tools/py/agf_stores.py`.",
           ' */',
           'export const KOTOR_STORES: Store[] = [']
    for ref, up, down, trade in rows:
        out.append(f'  {{ id: {q(ref)}, inventoryId: {q(ref + ":stock")}, markUpPercent: {up},'
                   f' markDownPercent: {down}, trade: {q(trade)} }},')
    out += ['];', '',
            '/** What each store starts with; an item without a count never runs out. */',
            'export const KOTOR_STORE_STOCK_ITEMS: StoreStockItem[] = [']
    for ref, _, _, _ in rows:
        counts, infinite = stock[ref]
        for item in sorted(set(counts) | infinite):
            if item in infinite:
                out.append(f'  {{ storeId: {q(ref)}, itemDefinitionId: {q(item)} }},')
            else:
                out.append(f'  {{ storeId: {q(ref)}, itemDefinitionId: {q(item)},'
                           f' itemCount: {counts[item]} }},')
    out += ['];', '']
    path = os.path.join(args.agf, 'apps', 'kotor', 'src', 'stores.ts')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(out))

    both = sorted((ref, item) for ref, (counts, infinite) in stock.items()
                  for item in infinite & set(counts))
    print(f'wrote {path}: {len(rows)} stores,'
          f' {sum(len(set(c) | i) for c, i in stock.values())} stock items,'
          f' {sum(len(i) for _, i in stock.values())} never running out')
    print(f'items both counted and never running out (written without a count): {both}')
    print(f'items left out: {len(unseeded)} templates, {sum(unseeded.values())} entries')
    for (ref, name), n in unseeded.most_common():
        print(f'    {ref} ({name}) x{n}')
    print(f'price mismatches: {len(price_mismatches)}')
    for m in sorted(price_mismatches):
        print('   ', m)


if __name__ == '__main__':
    main(sys.argv[1:])
