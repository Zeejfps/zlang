"""The engine routine table and constants from the game's own nwscript.nss (exploration only).

    python kotor/tools/py/nwscript.py            write docs/formats/nwscript-routines.tsv and
                                                 nwscript-constants.tsv, cross-check against the
                                                 NCS corpus, print a summary
    python kotor/tools/py/nwscript.py --no-usage the TSVs without the corpus columns (fast)

nwscript.nss is resource `nwscript` type nss, in data/scripts.bif (no Override copy in a stock
install; kres picks an Override copy first if one appears). Routine numbering is the declaration
order of the function prototypes, from 0; ACTION's u16 operand is that index.

As a library: load_routines() -> [Routine(index, ret, name, params, line)],
load_constants() -> [Constant(name, type, value, line)], cells(type) -> stack cells.
Only names, types and values are extracted: never the comment text.
"""

import os
import re
import sys
from collections import Counter, namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
KOTOR = os.path.dirname(os.path.dirname(HERE))
DOCS = os.path.join(KOTOR, 'docs', 'formats')

Routine = namedtuple('Routine', 'index ret name params line')
Param = namedtuple('Param', 'type name default written')
Constant = namedtuple('Constant', 'name type value line')

# One prototype (767, SetAvailableNPCId) spells its parameter types INT and OBJECT_ID; we read
# them as int and object.
TYPE_ALIASES = {'INT': 'int', 'OBJECT_ID': 'object'}
TYPES = {'void', 'int', 'float', 'string', 'object', 'vector', 'location', 'effect', 'event',
         'talent', 'action'}


def norm_type(t):
    t = TYPE_ALIASES.get(t, t)
    if t not in TYPES:
        raise ValueError(f'unknown nwscript type {t!r}')
    return t


def cells(t):
    """4-byte stack cells a value of type t occupies (as an ACTION argument or result)."""
    t = norm_type(t)
    return {'void': 0, 'vector': 3, 'action': 0}.get(t, 1)


_source = None


def source():
    """nwscript.nss text from the install (first in search order: Override wins)."""
    global _source
    if _source is None:
        import kres
        data = kres.Game().get('nwscript', 'nss')
        if data is None:
            raise SystemExit('nwscript.nss not found in the install')
        _source = data.decode('latin-1')
    return _source


def _strip(text):
    """Blank out comments and #define lines, keeping offsets (so line numbers survive)."""
    def blank(m):
        return re.sub(r'[^\n]', ' ', m.group(0))
    text = re.sub(r'/\*.*?\*/', blank, text, flags=re.S)
    text = re.sub(r'//[^\n]*', blank, text)
    text = re.sub(r'(?m)^[ \t]*#[^\n]*', blank, text)
    return text


def _split_top(s):
    """Split a parameter list on commas outside brackets (vector defaults are [x,y,z])."""
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch in '[(':
            depth += 1
        elif ch in '])':
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def _parse(text):
    stripped = _strip(text)
    routines, constants = [], []
    pos = 0
    for m in re.finditer(r';', stripped):
        stmt = stripped[pos:m.start()]
        start = pos + (len(stmt) - len(stmt.lstrip()))
        line = text.count('\n', 0, start) + 1
        pos = m.end()
        s = ' '.join(stmt.split())
        if not s:
            continue
        f = re.fullmatch(r'(\w+) (\w+) ?\((.*)\)', s)
        if f:
            params = []
            for p in _split_top(f.group(3)):
                p = p.strip()
                pm = re.fullmatch(r'(\w+) (\w+)(?: ?= ?(.+))?', p)
                if not pm:
                    raise ValueError(f'line {line}: cannot parse parameter {p!r}')
                default = pm.group(3).strip() if pm.group(3) else None
                written = f'{pm.group(1)} {pm.group(2)}' + (f'={default}' if default else '')
                norm_type(pm.group(1))
                params.append(Param(pm.group(1), pm.group(2), default, written))
            norm_type(f.group(1))
            routines.append(Routine(len(routines), f.group(1), f.group(2), params, line))
            continue
        c = re.fullmatch(r'(\w+) (\w+) ?= ?(.+)', s)
        if c:
            norm_type(c.group(1))
            constants.append(Constant(c.group(2), c.group(1), c.group(3).strip(), line))
            continue
        raise ValueError(f'line {line}: cannot parse statement {s[:60]!r}')
    return routines, constants


def load_routines(text=None):
    return _parse(text or source())[0]


def load_constants(text=None):
    return _parse(text or source())[1]


def index_comments(text):
    """(line, number) for each comment of the form '// N:', '// N.' or '// N' (BioWare numbered
    the prototypes in their comments; used only to cross-check our numbering)."""
    out = []
    for k, ln in enumerate(text.split('\n'), 1):
        m = re.match(r'\s*//\s*(\d+)\s*(?::|\.(?!\d)|$)', ln)
        if m:
            out.append((k, int(m.group(1))))
    return out


def check_numbering(text, routines):
    """Prototypes whose nearest preceding numbered comment disagrees with the declaration index."""
    marks = index_comments(text)
    bad, checked = [], 0
    j = -1
    for r in routines:
        while j + 1 < len(marks) and marks[j + 1][0] < r.line:
            j += 1
        if j >= 0:
            # Only a numbered comment between the previous prototype and this one counts.
            prev_line = routines[r.index - 1].line if r.index else 0
            if marks[j][0] > prev_line:
                checked += 1
                if marks[j][1] != r.index:
                    bad.append((r.index, r.name, marks[j][1]))
    return checked, bad


def constant_value(c, by_name):
    """Evaluate a constant's initializer: literal, or another constant's name (TRUE/FALSE)."""
    v = c.value
    if v in by_name:
        return constant_value(by_name[v], by_name)
    if c.type == 'float':
        return v.rstrip('fF')
    return v


def write_tsvs(routines, constants, usage=None):
    os.makedirs(DOCS, exist_ok=True)
    rp = os.path.join(DOCS, 'nwscript-routines.tsv')
    with open(rp, 'w', encoding='utf-8', newline='\n') as f:
        f.write('index\treturn\tname\tparams\tncs_files\tncs_sites\n')
        for r in routines:
            files, sites = ('', '')
            if usage is not None:
                u = usage.get(r.index)
                files, sites = (u[0], u[1]) if u else (0, 0)
            f.write(f'{r.index}\t{r.ret}\t{r.name}\t{", ".join(p.written for p in r.params)}'
                    f'\t{files}\t{sites}\n')
    cp = os.path.join(DOCS, 'nwscript-constants.tsv')
    by_name = {c.name: c for c in constants}
    with open(cp, 'w', encoding='utf-8', newline='\n') as f:
        f.write('name\ttype\tvalue\n')
        for c in constants:
            f.write(f'{c.name}\t{c.type}\t{constant_value(c, by_name)}\n')
    return rp, cp


# Argument-count mismatches that are understood: (routine, argc) -> explanation. All four come
# from scripts compiled against a different nwscript.nss than the one shipped (see
# docs/formats/nwscript.md, "Checked").
KNOWN_ARGC = {
    (469, 2): 'nw_s0_lghtnbolt: GetIsReactionTypeFriendly(oTarget[, oSource]) in an older table',
    (518, 2): 'k_creditsplay (STUNT_57): an older StartCreditSequence with a second argument',
    (574, 1): 'k_act_carthjoin, k_ptar_missjoin (Taris): an older AddPartyMember(object)',
    (700, 2): 'k_plev_corpse1 (lev_m40aa): an older ActionBarkString(object, int)',
}


def cross_check(routines, usage):
    """ACTION indices in range; each observed argument count between the routine's required
    parameter count and its total. Returns (problems, explained)."""
    problems, explained = [], []
    if usage:
        top = max(usage)
        if top >= len(routines):
            problems.append(f'max ACTION index {top} >= routine count {len(routines)}')
    for rid, (_files, _sites, argc) in sorted(usage.items()):
        if rid >= len(routines):
            continue
        r = routines[rid]
        required = sum(1 for p in r.params if p.default is None)
        for a, n in argc.items():
            if not required <= a <= len(r.params):
                msg = (f'{rid} {r.name}: called with {a} args ({n} sites); '
                       f'takes {required}..{len(r.params)}')
                if (rid, a) in KNOWN_ARGC:
                    explained.append(f'{msg}; explained: {KNOWN_ARGC[(rid, a)]}')
                else:
                    problems.append(msg)
    return problems, explained


def main(argv):
    if argv and argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    text = source()
    routines, constants = _parse(text)
    checked, bad = check_numbering(text, routines)
    usage = None
    ncs_files = None
    if '--no-usage' not in argv:
        import ncsdis
        usage, ncs_files = ncsdis.action_usage()
    rp, cp = write_tsvs(routines, constants, usage)
    print(f'routines: {len(routines)}   constants: {len(constants)}')
    print(f'returns: {dict(Counter(r.ret for r in routines).most_common())}')
    ptypes = Counter(norm_type(p.type) for r in routines for p in r.params)
    print(f'parameter types: {dict(ptypes.most_common())}')
    print(f'constant types: {dict(Counter(c.type for c in constants).most_common())}')
    print(f'numbered comments checked against declaration order: {checked}, disagreeing: {len(bad)}')
    for b in bad:
        print(f'  routine {b[0]} {b[1]}: comment says {b[2]}')
    odd = [(r.index, r.name, p.written) for r in routines for p in r.params
           if p.type in TYPE_ALIASES]
    if odd:
        print(f'non-standard parameter type spellings: {odd}')
    print(f'wrote {rp}\nwrote {cp}')
    if usage is None:
        return 0
    problems, explained = cross_check(routines, usage)
    used = [r for r in routines if r.index in usage]
    print(f'NCS files (unique resref+content): {ncs_files}; routines used: {len(used)}; '
          f'never used: {len(routines) - len(used)}; max index used: {max(usage)}')
    print(f'cross-check problems: {len(problems)} (plus {len(explained)} explained)')
    for p in problems:
        print('  ' + p)
    for p in explained:
        print('  ' + p)
    short = sum(n for r in routines if r.index in usage
                for a, n in usage[r.index][2].items() if a < len(r.params))
    print(f'ACTION sites passing fewer arguments than the routine declares: {short}')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
