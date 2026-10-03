"""Dump the script situations (saved actions and DelayCommands) of the install's save games, so
the VM can resume them (exploration only; see docs/formats/gff-save.md, "Script situation").

    python kotor/tools/py/ncssituations.py [OUT_DIR]       default kotor/out/situations

For each situation in each save's module states (the IFO's EventQueue, and every object's
ActionList parameter of type 5), it writes NAME.ncs (the saved Code behind a 13-byte NCS
header) and NAME.sit, which `ncsrun --situation NAME.sit` reads:

    u32 InstructionPtr, u32 BasePointer, u32 StackSize, u32 cells,
    then per cell: u8 Type, and a u32 value, or for a string (Type 5) a u32 length and the bytes

all little-endian. An engine structure's value is its index among the situation's cells, a
stand-in handle (the stub engine has no effects to give it). NAME is the save, the module, where
the situation was found and the script's name.
"""

import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KOTOR = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import gff  # noqa: E402
import kres  # noqa: E402


def situation(s):
    """(name, code, ip, bp, stack_size, cells) of a script situation struct."""
    code = s.get('Code') or b''
    stack = s.get('Stack')
    cells = []
    bp = 0
    if stack is not None:
        bp = stack.get('BasePointer')
        for c in stack.get('Stack') or []:
            t = c.get('Type')
            if t == 5:
                cells.append((t, c.get('Value')))
            elif t >= 0x10:
                cells.append((t, len(cells)))
            elif t == 4:
                cells.append((t, struct.unpack('<I', struct.pack('<f', c.get('Value')))[0]))
            else:
                cells.append((t, c.get('Value') & 0xFFFFFFFF))
    return s.get('Name').decode('latin-1'), code, s.get('InstructionPtr'), bp, s.get('StackSize'), cells


def found(g, where):
    """Every script situation in a module state GFF, with where it was."""
    out = []
    root = g.root
    for i, ev in enumerate(root.get('EventQueue') or []):
        if ev.get('EventId') == 1 and ev.get('EventData') is not None:
            out.append((f'event{i}', ev.get('EventData')))

    def walk(s, path):
        for f in s.fields:
            if f.type == gff.LIST:
                for k, e in enumerate(f.value):
                    if f.label == 'ActionList':
                        for n, p in enumerate(e.get('Paramaters') or []):
                            if p.get('Type') == 5:
                                out.append((f'{path}action{k}.{n}', p.get('Value')))
                    walk(e, f'{path}{f.label.replace(" ", "")}{k}.')
            elif f.type == gff.STRUCT:
                walk(f.value, f'{path}{f.label}.')
    walk(root, '')
    return out


def write(out, name, sit):
    script, code, ip, bp, stack_size, cells = sit
    with open(os.path.join(out, name + '.ncs'), 'wb') as f:
        f.write(b'NCS V1.0B' + struct.pack('>I', 13 + len(code)) + code)
    b = bytearray(struct.pack('<4I', ip, bp, stack_size, len(cells)))
    for t, v in cells:
        b += bytes([t])
        if t == 5:
            b += struct.pack('<I', len(v)) + v
        else:
            b += struct.pack('<I', v)
    with open(os.path.join(out, name + '.sit'), 'wb') as f:
        f.write(bytes(b))


def main(argv):
    out = argv[0] if argv else os.path.join(KOTOR, 'out', 'situations')
    os.makedirs(out, exist_ok=True)
    g = kres.Game()
    saves = os.path.join(g.dir, 'Saves')
    n = 0
    for save in sorted(os.listdir(saves)):
        path = os.path.join(saves, save, 'SAVEGAME.sav')
        if not os.path.isfile(path):
            continue
        tag = re.sub(r'\W+', '_', save).strip('_')
        for e in kres.read_container(path):
            if e.ext != 'sav':
                continue
            for inner in kres.read_container(path, e.offset):
                if inner.ext not in ('ifo', 'git'):
                    continue
                data = kres.read_entry(inner)
                for where, s in found(gff.read(data), inner.ext):
                    sit = situation(s)
                    name = f'{tag}-{e.resref}-{inner.ext}-{where}-{sit[0]}'
                    write(out, name, sit)
                    print(f'{name}: {sit[0]}, {len(sit[1])} bytes of code, resume at {sit[2]}, '
                          f'BP {sit[3]}, {len(sit[5])} cells, StackSize {sit[4]}')
                    n += 1
    print(f'{n} situations written to {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
