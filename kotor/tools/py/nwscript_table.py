"""Map NWScript engine routine numbers to their handlers in swkotor.exe (dev tooling).

The game's VM dispatches routine N (the ACTION opcode's operand) through a table of 772
function pointers that one function fills at start-up, slot by slot, with stores of the form
`MOV dword ptr [reg + 4*N], handler` (the table pointer is reloaded from [ESI+0xc] each time).
See kotor/docs/re/nwscript-routines.md. This script replays those stores from the function's
disassembly, pairs each slot with the Nth prototype in nwscript.nss, and writes

    kotor/re/export/nwscript_routines.tsv     number, name, handler, ... (git-ignored)

With --names it also adds a row per handler to kotor/docs/re/names.tsv (our names, committed).

    python kotor/tools/py/nwscript_table.py [--names] [--init ADDR]
"""

import argparse
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rex  # noqa: E402

# The function that fills the table (CSWVirtualMachineCommands::InitializeCommands, our name).
INIT_ADDR = 0x0054c960
ROUTINE_COUNT = 772
CLASS = 'CSWVirtualMachineCommands'

TYPES = ('int', 'void', 'float', 'object', 'string', 'location', 'vector', 'effect', 'event',
         'talent', 'action', 'itemproperty')
PROTO_RX = re.compile(r'^\s*(' + '|'.join(TYPES) + r')\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)\s*;')


def read_routines(nss_text):
    """(number, return type, name, params) for each engine routine prototype, in order.

    Engine routines are the prototypes without a body; nwscript.nss holds nothing else of
    that shape, and its comments number them ("// 12: ...") which we check against."""
    out = []
    last_num = None
    for line in nss_text.splitlines():
        m = re.match(r'^\s*//\s*(\d+)\s*:', line)
        if m:
            last_num = int(m.group(1))
            continue
        m = PROTO_RX.match(line)
        if m:
            n = len(out)
            if last_num is not None and last_num != n:
                print(f'warning: nwscript.nss comment says {last_num} for {m.group(2)}, '
                      f'position is {n}', file=sys.stderr)
            out.append((n, m.group(1), m.group(2), m.group(3).strip()))
            last_num = None
    return out


def nss_text():
    path = os.path.join(rex.RE, 'data', 'nwscript.nss')
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        subprocess.run([sys.executable, os.path.join(HERE, 'kres.py'), 'get', 'nwscript.nss',
                        '-o', path], check=True)
    with open(path, encoding='latin-1') as f:
        return f.read()


def listing(addr):
    hits = glob.glob(os.path.join(rex.EXPORT, 'asm', f'{addr:08x}_*.s'))
    if not hits:
        subprocess.run([sys.executable, os.path.join(HERE, 'rex.py'), 'asm', hex(addr)],
                       check=True, stdout=subprocess.DEVNULL)
        hits = glob.glob(os.path.join(rex.EXPORT, 'asm', f'{addr:08x}_*.s'))
    with open(hits[0], encoding='utf-8') as f:
        return f.read().splitlines()


REG = r'(EAX|EBX|ECX|EDX|ESI|EDI|EBP)'
LOAD_TABLE = re.compile(r'MOV ' + REG + r',dword ptr \[' + REG + r' \+ 0xc\]$')
LOAD_IMM = re.compile(r'MOV ' + REG + r',0x([0-9a-f]+)$')
COPY = re.compile(r'MOV ' + REG + r',' + REG + r'$')
STORE = re.compile(r'MOV dword ptr \[' + REG + r'(?: \+ 0x([0-9a-f]+))?\],(?:0x([0-9a-f]+)|' + REG
                   + r')$')
TAIL = re.compile(r'JMP 0x([0-9a-f]+)$')
WRITES_REG = re.compile(r'^[A-Z]+ ' + REG + r'\b')


def replay(addr, slots, seen):
    """Fill slots (slot -> handler address) from a table-filling function's stores, following
    tail jumps into the next such function (the minigame routines are filled by a second one).
    On entry ECX is the commands object; the table pointer is at this+0xc."""
    if addr in seen:
        return
    seen.add(addr)
    regs = {'ECX': 'THIS'}   # register -> int constant, 'THIS' or 'TABLE'
    tails = []
    for line in listing(addr):
        m = re.match(r'^\s+[0-9a-f]{8}\s+[0-9a-f]+\s+(.*?)(?:\s+;.*)?$', line)
        if not m:
            continue
        ins = m.group(1).strip()
        if (mm := LOAD_TABLE.match(ins)) and regs.get(mm.group(2)) == 'THIS':
            regs[mm.group(1)] = 'TABLE'
        elif (mm := LOAD_IMM.match(ins)):
            regs[mm.group(1)] = int(mm.group(2), 16)
        elif (mm := COPY.match(ins)):
            if mm.group(2) in regs:
                regs[mm.group(1)] = regs[mm.group(2)]
            else:
                regs.pop(mm.group(1), None)
        elif (mm := STORE.match(ins)):
            base, disp, imm, src = mm.groups()
            if regs.get(base) != 'TABLE':
                continue
            value = int(imm, 16) if imm else regs.get(src)
            if not isinstance(value, int):
                continue
            off = int(disp, 16) if disp else 0
            slots[off // 4] = value
        elif (mm := TAIL.match(ins)):
            target = int(mm.group(1), 16)
            if not (addr <= target < addr + 0x10000):   # a jump out of the function
                tails.append(target)
        elif ins.startswith('CALL'):
            for r in ('EAX', 'ECX', 'EDX'):
                regs.pop(r, None)
        elif (mm := WRITES_REG.match(ins)):
            regs.pop(mm.group(1), None)
    for t in tails:
        print(f'following tail jump to {t:#010x}', file=sys.stderr)
        replay(t, slots, seen)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--names', action='store_true', help='add handler names to names.tsv')
    ap.add_argument('--init', default=hex(INIT_ADDR), help='address of the table-filling function')
    args = ap.parse_args()

    routines = read_routines(nss_text())
    if len(routines) != ROUTINE_COUNT:
        print(f'warning: nwscript.nss has {len(routines)} routines, expected {ROUTINE_COUNT}',
              file=sys.stderr)
    slots = {}
    seen = set()
    replay(int(args.init, 16), slots, seen)
    idx = rex.Index()
    handlers = {}
    for n, h in slots.items():
        handlers.setdefault(h, []).append(n)

    out = os.path.join(rex.EXPORT, 'nwscript_routines.tsv')
    missing = []
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('number\tname\thandler\thandler_name\tshared_with\tsignature\n')
        for n, ret, name, params in routines:
            h = slots.get(n)
            if h is None:
                missing.append(n)
            shared = [str(k) for k in sorted(handlers.get(h, [])) if k != n] if h else []
            f.write(f'{n}\t{name}\t{rex.hx(h) if h else ""}\t{idx.name(h) if h else ""}\t'
                    f'{",".join(shared)}\t{ret} {name}({params})\n')
    print(f'{len(slots)} slots filled, {len(handlers)} distinct handlers, '
          f'{len(missing)} routines without a handler {missing[:20]}; wrote {out}')

    if args.names:
        by_num = {n: (ret, name, params) for n, ret, name, params in routines}
        rows = [(rex.hx(int(args.init, 16)), f'{CLASS}::InitializeCommands', '',
                 'fills the 772-slot engine routine table (this+0xc); see nwscript-routines.md')]
        for extra in sorted(seen - {int(args.init, 16)}):
            rows.append((rex.hx(extra), f'{CLASS}::InitializeMiniGameCommands', '',
                         'tail-called by InitializeCommands; fills the SWMG_* minigame slots'))
        # The linker folded identical functions, so a trivial handler (e.g. one that only
        # returns 0) can be the same code as unrelated virtual functions. Those get a neutral
        # name so vtables of other classes don't appear to hold script commands.
        used_elsewhere = set()
        for c in rex.read_tsv('calls.tsv'):
            if int(c['caller'], 16) not in seen:
                used_elsewhere.add(int(c['callee'], 16))
        for t in rex.read_tsv('vtables.tsv'):
            for e in t['entries'].split(','):
                used_elsewhere.add(int(e.split('=')[0], 16))
        for h, nums in sorted(handlers.items()):
            nums.sort()
            first = by_num[nums[0]][1] if nums[0] in by_num else f'Routine{nums[0]}'
            listed = ', '.join(f'{k} {by_num[k][1]}' for k in nums if k in by_num)
            if h in used_elsewhere:
                rows.append((rex.hx(h), f'FoldedStub_{h:08x}', '',
                             f'linker-folded trivial function, also used outside the script '
                             f'commands; as a NWScript handler it serves: {listed}'))
                continue
            comment = f'NWScript routine {listed}' if len(nums) == 1 else \
                f'NWScript routines (shared handler, switches on nCommand): {listed}'
            rows.append((rex.hx(h), f'{CLASS}::ExecuteCommand{first}',
                         'int __thiscall ExecuteCommand(int nCommand, int nParameters)', comment))
        n = rex.upsert_names(rows, overwrite=True)
        print(f'{n} rows added or changed in {rex.NAMES}')


if __name__ == '__main__':
    main()
