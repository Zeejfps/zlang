"""Compare two exports of swkotor.exe (dev tooling): which functions appeared, vanished or
decompile differently, and which of those the docs already cite.

    export_diff.py OLD_EXPORT NEW_EXPORT [--out DIR]

OLD/NEW are export directories (kotor/re/export_prev, kotor/re/export). Writes two TSVs into
DIR (default kotor/docs/re): noreturn-fix-functions.tsv (one row per function that appeared,
vanished or whose decompiled body changed) and noreturn-fix-recheck.tsv (one row per doc that
cites such a function). A doc "cites" a function when it mentions the entry address or an
address inside the body; names.tsv counts as a doc. Only the decompiled body is compared, not
the comment header, so renamed callers and new caller lists do not show as changes.
"""

import argparse
import bisect
import collections
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'docs')
TEXT = (0x401000, 0x73c1d0)


def load_bodies(export):
    """address -> (name, body lines); the body starts after the `//` header."""
    out = {}
    fdir = os.path.join(export, 'functions')
    for fn in os.listdir(fdir):
        with open(os.path.join(fdir, fn), encoding='utf-8') as f:
            lines = f.read().split('\n')
        name = re.match(r'// 0x[0-9a-f]+\s+(\S+)', lines[0]) if lines else None
        i = 0
        while i < len(lines) and (lines[i].startswith('//') or not lines[i].strip()):
            i += 1
        body = lines[i:]
        while body and not body[-1].strip():
            body.pop()
        out[int(fn[:8], 16)] = (name.group(1) if name else fn[9:-2], body)
    return out


def load_index(export):
    out = {}
    with open(os.path.join(export, 'functions.tsv'), encoding='utf-8') as f:
        next(f)
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) > 8:
                out[int(p[0], 16)] = p
    return out


def load_mentions(docs):
    """address -> set of docs (relative paths) that mention it"""
    files = (sorted(glob.glob(os.path.join(docs, 're', '*.md')))
             + sorted(glob.glob(os.path.join(docs, 'mechanics', '*.md')))
             + [os.path.join(docs, 're', 'names.tsv')])
    hexre = re.compile(r'(?<![0-9a-zA-Z_])(0x)?([0-9a-fA-F]{6,8})(?![0-9a-zA-Z_])')
    out = collections.defaultdict(set)
    for path in files:
        rel = os.path.relpath(path, docs).replace('\\', '/')
        with open(path, encoding='utf-8', errors='replace') as f:
            for line in f:
                for m in hexre.finditer(line):
                    tok = m.group(2)
                    if not m.group(1) and len(tok) != 8 and not re.search('[a-fA-F]', tok):
                        continue   # a plain number, not an address
                    v = int(tok, 16)
                    if TEXT[0] <= v < TEXT[1]:
                        out[v].add(rel)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('old')
    ap.add_argument('new')
    ap.add_argument('--out', default=os.path.join(DOCS, 're'))
    ap.add_argument('--docs', default=DOCS)
    args = ap.parse_args()

    old, new = load_bodies(args.old), load_bodies(args.new)
    oidx, nidx = load_index(args.old), load_index(args.new)
    mentions = load_mentions(args.docs)
    mentioned = sorted(mentions)

    def cited_in(entry, size):
        docs = set(mentions.get(entry, ()))
        k = bisect.bisect_left(mentioned, entry)
        while k < len(mentioned) and mentioned[k] < entry + max(size, 1):
            docs |= mentions[mentioned[k]]
            k += 1
        return sorted(docs)

    new_entries = sorted(new)
    rows = []   # kind, addr, name, before, after, docs, note
    for a in sorted(set(old) | set(new)):
        if a in old and a in new:
            if old[a][1] != new[a][1]:
                rows.append(('changed', a, new[a][0], len(old[a][1]), len(new[a][1]),
                             cited_in(a, int(nidx[a][2])), ''))
        elif a in new:
            rows.append(('new', a, new[a][0], '', len(new[a][1]),
                         cited_in(a, int(nidx[a][2])), nidx[a][6]))
        else:
            k = bisect.bisect_right(new_entries, a) - 1
            e = new_entries[k]
            inside = (f'now inside 0x{e:08x} {new[e][0]}'
                      if k >= 0 and a < e + int(nidx[e][2]) else '')
            rows.append(('gone', a, old[a][0], len(old[a][1]), '',
                         cited_in(a, int(oidx[a][2])), inside))

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, 'noreturn-fix-functions.tsv')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('kind\taddr\tname\tlines_before\tlines_after\tcited_in\tnote\n')
        for kind, a, name, b, c, docs, note in rows:
            f.write(f'{kind}\t0x{a:08x}\t{name}\t{b}\t{c}\t{" ".join(docs)}\t{note}\n')

    def growth(r):
        return (r[4] if r[4] != '' else 0) - (r[3] if r[3] != '' else 0)

    per_doc = collections.defaultdict(list)
    for r in rows:
        for d in r[5]:
            per_doc[d].append(r)
    path2 = os.path.join(args.out, 'noreturn-fix-recheck.tsv')
    with open(path2, 'w', encoding='utf-8', newline='\n') as f:
        f.write('doc\tkind\taddr\tname\tlines_before\tlines_after\n')
        for d in sorted(per_doc):
            for kind, a, name, b, c, docs, note in sorted(per_doc[d], key=lambda r: (-abs(growth(r)), r[1])):
                f.write(f'{d}\t{kind}\t0x{a:08x}\t{name}\t{b}\t{c}\n')

    kinds = collections.Counter(r[0] for r in rows)
    cited = collections.Counter(r[0] for r in rows if r[5])
    print(f'functions: old {len(old)}, new {len(new)}')
    for k in ('changed', 'new', 'gone'):
        print(f'{k}: {kinds[k]}, cited by a doc: {cited[k]}')
    print('docs citing them:', {d: len(v) for d, v in sorted(per_doc.items())})
    print(f'wrote {path} and {path2}')


if __name__ == '__main__':
    sys.stdout.reconfigure(errors='replace')
    main()
