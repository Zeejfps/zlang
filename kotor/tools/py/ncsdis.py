"""NCS (compiled NWScript) disassembler and corpus checker, for exploration (not used by the game).

    python kotor/tools/py/ncsdis.py FILE.ncs | RESREF       disassemble one script to text
        -x                    show each instruction's raw bytes
        --no-names            don't annotate ACTION with routine names from nwscript.nss
    python kotor/tools/py/ncsdis.py --corpus [-o STATS.txt] [--no-stack]
        disassemble every NCS copy in the install (BIFs, module RIMs/MODs, rims/, Override, saves),
        validate each, and print usage statistics (default output: kotor/extract/ncs-stats.txt)

Validation per file: the "NCS V1.0" magic, the 0x42 byte, the big-endian file size equal to the
real size, every instruction decodes to a known (opcode, type) pair with its operands inside the
file, the last instruction ends exactly at the end of the file, and every JMP/JSR/JZ/JNZ target
and every STORE_STATE resume point lands on an instruction boundary. Unless --no-stack, it also
walks every routine and deferred block tracking the stack depth (ACTION effects from the routine
signatures in nwscript.nss) and checks that every path agrees: see check_stack.

Format notes: kotor/docs/formats/ncs.md.
"""

import hashlib
import os
import struct
import sys
from collections import Counter, defaultdict, namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
KOTOR = os.path.dirname(os.path.dirname(HERE))
DEFAULT_STATS = os.path.join(KOTOR, 'extract', 'ncs-stats.txt')

HEADER = b'NCS V1.0'
HEADER_SIZE = 13  # magic, the 0x42 byte, u32 big-endian file size

# Opcode -> mnemonic.
OPS = {
    0x01: 'CPDOWNSP', 0x02: 'RSADD', 0x03: 'CPTOPSP', 0x04: 'CONST', 0x05: 'ACTION',
    0x06: 'LOGAND', 0x07: 'LOGOR', 0x08: 'INCOR', 0x09: 'EXCOR', 0x0A: 'BOOLAND',
    0x0B: 'EQUAL', 0x0C: 'NEQUAL', 0x0D: 'GEQ', 0x0E: 'GT', 0x0F: 'LT', 0x10: 'LEQ',
    0x11: 'SHLEFT', 0x12: 'SHRIGHT', 0x13: 'USHRIGHT',
    0x14: 'ADD', 0x15: 'SUB', 0x16: 'MUL', 0x17: 'DIV', 0x18: 'MOD', 0x19: 'NEG', 0x1A: 'COMP',
    0x1B: 'MOVSP', 0x1C: 'STORE_STATEALL', 0x1D: 'JMP', 0x1E: 'JSR', 0x1F: 'JZ', 0x20: 'RETN',
    0x21: 'DESTRUCT', 0x22: 'NOT', 0x23: 'DECISP', 0x24: 'INCISP', 0x25: 'JNZ',
    0x26: 'CPDOWNBP', 0x27: 'CPTOPBP', 0x28: 'DECIBP', 0x29: 'INCIBP',
    0x2A: 'SAVEBP', 0x2B: 'RESTOREBP', 0x2C: 'STORE_STATE', 0x2D: 'NOP',
}

# Type byte -> suffix. Unary types name the operand, binary ones both operands (left, right).
TYPES = {
    0x00: '', 0x01: '', 0x03: 'I', 0x04: 'F', 0x05: 'S', 0x06: 'O',
    0x10: 'EFFECT', 0x11: 'EVENT', 0x12: 'LOCATION', 0x13: 'TALENT',
    0x20: 'II', 0x21: 'FF', 0x22: 'OO', 0x23: 'SS', 0x24: 'TT', 0x25: 'IF', 0x26: 'FI',
    0x30: 'EFFECTEFFECT', 0x31: 'EVENTEVENT', 0x32: 'LOCLOC', 0x33: 'TALTAL',
    0x3A: 'VV', 0x3B: 'VF', 0x3C: 'FV',
}

ARITH = {0x20, 0x21, 0x25, 0x26}
ENGINE_PAIRS = {0x30, 0x31, 0x32, 0x33}
# Which type bytes each opcode may carry (the full theoretical set, so the corpus statistics
# show which ones the compiler actually emitted). A pair outside this table fails validation.
ALLOWED = {
    0x01: {0x01}, 0x02: {0x03, 0x04, 0x05, 0x06, 0x10, 0x11, 0x12, 0x13}, 0x03: {0x01},
    0x04: {0x03, 0x04, 0x05, 0x06}, 0x05: {0x00},
    0x06: {0x20}, 0x07: {0x20}, 0x08: {0x20}, 0x09: {0x20}, 0x0A: {0x20},
    0x0B: {0x20, 0x21, 0x22, 0x23, 0x24} | ENGINE_PAIRS,
    0x0C: {0x20, 0x21, 0x22, 0x23, 0x24} | ENGINE_PAIRS,
    0x0D: {0x20, 0x21}, 0x0E: {0x20, 0x21}, 0x0F: {0x20, 0x21}, 0x10: {0x20, 0x21},
    0x11: {0x20}, 0x12: {0x20}, 0x13: {0x20},
    0x14: ARITH | {0x23, 0x3A}, 0x15: ARITH | {0x3A}, 0x16: ARITH | {0x3B, 0x3C},
    0x17: ARITH | {0x3B}, 0x18: {0x20}, 0x19: {0x03, 0x04}, 0x1A: {0x03},
    0x1B: {0x00}, 0x1D: {0x00}, 0x1E: {0x00}, 0x1F: {0x00}, 0x20: {0x00},
    0x21: {0x01}, 0x22: {0x03}, 0x23: {0x03}, 0x24: {0x03}, 0x25: {0x00},
    0x26: {0x01}, 0x27: {0x01}, 0x28: {0x03}, 0x29: {0x03},
    0x2A: {0x00}, 0x2B: {0x00}, 0x2C: {0x10}, 0x2D: {0x00},
}

JUMPS = {0x1D, 0x1E, 0x1F, 0x25}  # JMP JSR JZ JNZ: i32 offset relative to the instruction

# Stack-check failures that are understood (see kotor/docs/formats/ncs.md, "Checked"). Keyed by
# resref; the value is the explanation printed instead of failing the run.
KNOWN_STACK = {
    'nw_s0_lghtnbolt': 'an early test spell script; its shipped source calls '
                       'GetIsReactionTypeFriendly(oTarget), which the shipped nwscript.nss no '
                       'longer declares: the NCS was compiled against an older table in which '
                       '469 was that 2-parameter routine',
    'k_creditsplay': 'calls StartCreditSequence (518) with 2 arguments; the shipped nwscript.nss '
                     'declares 1 (compiled against an older nwscript.nss)',
    'k_plev_corpse1': 'calls ActionBarkString (700) with 2 arguments (an object, then strref '
                      '1075); the shipped nwscript.nss declares 1 int (compiled against an older '
                      'nwscript.nss)',
    'k_ptar_drunk_ud': "compiler bug: a string local declared inside a switch case is never "
                       "popped (the case's break jumps over the MOVSP), so one path reaches the "
                       "end of the switch one cell deeper than the others",
}

Instr = namedtuple('Instr', 'offset op type args size')


class NcsError(Exception):
    pass


def check_header(data):
    if len(data) < HEADER_SIZE:
        raise NcsError(f'file is {len(data)} bytes, shorter than the {HEADER_SIZE}-byte header')
    if data[:8] != HEADER:
        raise NcsError(f'bad magic {data[:8]!r}')
    if data[8] != 0x42:
        raise NcsError(f'byte 8 is 0x{data[8]:02x}, not 0x42')
    size = struct.unpack_from('>I', data, 9)[0]
    if size != len(data):
        raise NcsError(f'header says {size} bytes, file is {len(data)}')


def decode_one(data, p):
    """The instruction at byte offset p. Raises NcsError if it is unknown or runs off the end."""
    end = len(data)
    if p + 2 > end:
        raise NcsError(f'{p:08x}: instruction header runs off the end')
    op, ty = data[p], data[p + 1]
    if op not in OPS:
        raise NcsError(f'{p:08x}: unknown opcode 0x{op:02x}')
    allowed = ALLOWED.get(op)
    if allowed is None or ty not in allowed:
        raise NcsError(f'{p:08x}: {OPS[op]} with unexpected type byte 0x{ty:02x}')
    q = p + 2

    def need(n):
        if q + n > end:
            raise NcsError(f'{p:08x}: {OPS[op]} operands run off the end')

    if op in (0x01, 0x03, 0x26, 0x27):           # CPDOWNSP CPTOPSP CPDOWNBP CPTOPBP
        need(6)
        args = struct.unpack_from('>iH', data, q)
        q += 6
    elif op == 0x04:                               # CONST
        if ty == 0x05:
            need(2)
            n = struct.unpack_from('>H', data, q)[0]
            q += 2
            need(n)
            args = (data[q:q + n].decode('latin-1'),)
            q += n
        elif ty == 0x04:
            need(4)
            args = struct.unpack_from('>f', data, q)
            q += 4
        else:                                      # int, object
            need(4)
            args = struct.unpack_from('>i', data, q)
            q += 4
    elif op == 0x05:                               # ACTION routine, argument count
        need(3)
        args = struct.unpack_from('>HB', data, q)
        q += 3
    elif op in (0x0B, 0x0C) and ty == 0x24:        # EQUALTT/NEQUALTT size in bytes
        need(2)
        args = struct.unpack_from('>H', data, q)
        q += 2
    elif op in (0x1B, 0x23, 0x24, 0x28, 0x29) or op in JUMPS:
        need(4)
        args = struct.unpack_from('>i', data, q)
        q += 4
    elif op == 0x21:                               # DESTRUCT size, keep offset, keep size
        need(6)
        args = struct.unpack_from('>HhH', data, q)
        q += 6
    elif op == 0x2C:                               # STORE_STATE BP bytes, SP bytes
        need(8)
        args = struct.unpack_from('>ii', data, q)
        q += 8
    else:
        args = ()
    return Instr(p, op, ty, args, q - p)


def decode(data):
    """Validate the header and decode the whole program. Returns the instruction list."""
    check_header(data)
    out = []
    p = HEADER_SIZE
    end = len(data)
    while p < end:
        ins = decode_one(data, p)
        out.append(ins)
        p += ins.size
    if p != end:  # unreachable as written; kept as the stated invariant
        raise NcsError(f'code ends at {p}, file at {end}')
    return out


def check_targets(instrs):
    """Every jump target and STORE_STATE resume point must be an instruction start."""
    starts = {i.offset for i in instrs}
    errs = []
    for k, i in enumerate(instrs):
        if i.op in JUMPS:
            t = i.offset + i.args[0]
            if t not in starts:
                errs.append(f'{i.offset:08x}: {OPS[i.op]} target {t:08x} is not an instruction start')
        elif i.op == 0x2C:
            t = i.offset + i.type
            if t not in starts:
                errs.append(f'{i.offset:08x}: STORE_STATE resume point {t:08x} is not an instruction start')
            nxt = instrs[k + 1] if k + 1 < len(instrs) else None
            if nxt is None or nxt.op != 0x1D:
                errs.append(f'{i.offset:08x}: STORE_STATE not followed by JMP')
    return errs


def mnemonic(i):
    if i.op == 0x2C:  # its type byte is the resume offset, not a type
        return OPS[i.op]
    return OPS[i.op] + TYPES.get(i.type, f'?{i.type:02x}')


def format_instr(i, data=None, names=None, labels=None):
    m = mnemonic(i)
    if i.op in JUMPS:
        t = i.offset + i.args[0]
        a = f'{i.args[0]:+d}'.ljust(10) + f'; -> {labels.get(t, f"{t:08x}") if labels else f"{t:08x}"}'
    elif i.op == 0x04 and i.type == 0x05:
        a = repr(i.args[0])
    elif i.op == 0x04 and i.type == 0x04:
        a = repr(i.args[0])
    elif i.op == 0x05:
        n = names[i.args[0]] if names and i.args[0] < len(names) else ''
        a = f'{i.args[0]} {i.args[1]}'.ljust(10) + (f'; {n}' if n else '')
    elif i.op == 0x2C:
        a = f'{i.args[0]} {i.args[1]}'.ljust(10) + f'; resume at {i.offset + i.type:08x}'
    else:
        a = ' '.join(str(x) for x in i.args)
    line = f'{i.offset:08x}  {m:<16} {a}'.rstrip()
    if data is not None:
        line = f'{data[i.offset:i.offset + i.size].hex(" "):<30} ' + line
    return line


def routine_names():
    try:
        import nwscript
        return [r.name for r in nwscript.load_routines()]
    except Exception:
        return None


def deferred_shapes(instrs, shapes, consumers):
    """For each STORE_STATE: the deferred block's straight-line body, and which routine takes
    the saved state (the first ACTION after the JMP whose routine has an action parameter)."""
    acts = action_param_routines()
    by_off = {i.offset: k for k, i in enumerate(instrs)}
    for k, i in enumerate(instrs):
        if i.op != 0x2C:
            continue
        body = []
        j = by_off.get(i.offset + i.type)
        while j is not None and j < len(instrs) and len(body) < 40:
            m = mnemonic(instrs[j])
            if instrs[j].op == 0x05:
                m += f'({instrs[j].args[0]})'
            body.append(m)
            if instrs[j].op == 0x20:
                break
            j += 1
        collapsed = []
        for m in body:
            if collapsed and collapsed[-1].rstrip('+') == m:
                collapsed[-1] = m + '+'
            else:
                collapsed.append(m)
        shapes[' '.join(collapsed if len(collapsed) < 12 else collapsed[:11] + ['...'])] += 1
        jmp = instrs[k + 1]
        j = by_off.get(jmp.offset + jmp.args[0])
        name = 'none found'
        depth = 0
        while j is not None and j < len(instrs):
            x = instrs[j]
            if x.op == 0x2C:
                depth += 1
            if x.op == 0x05 and x.args[0] in acts:
                if depth == 0:
                    name = acts[x.args[0]]
                    break
                depth -= 1
            if x.op in (0x1D, 0x20):
                break
            j += 1
        consumers[name] += 1


_acts = None


def action_param_routines():
    global _acts
    if _acts is None:
        import nwscript
        _acts = {r.index: r.name for r in nwscript.load_routines()
                 if any(nwscript.norm_type(p.type) == 'action' for p in r.params)}
    return _acts


def program_layout(instrs):
    """Classify the program's start as BioWare's compiler lays it out:
        [RSADDI] JSR x; RETN                         entry (RSADDI: StartingConditional's result)
        x: (RSADDx; init; CPDOWNSP; MOVSP)* SAVEBP [RSADDI] JSR main ... RESTOREBP MOVSP RETN
                                                     only when there are global variables
    Returns e.g. 'StartingConditional, globals' or 'other: ...'."""
    by_off = {i.offset: k for k, i in enumerate(instrs)}
    k = 0
    cond = instrs[0].op == 0x02 and instrs[0].type == 0x03
    if cond:
        k = 1
    if k + 1 >= len(instrs) or instrs[k].op != 0x1E or instrs[k + 1].op != 0x20:
        return 'other: ' + ' '.join(mnemonic(i) for i in instrs[:4])
    kind = 'StartingConditional' if cond else 'void main'
    j = by_off[instrs[k].offset + instrs[k].args[0]]
    while instrs[j].op not in (0x1E, 0x1D, 0x1F, 0x25, 0x20, 0x2A):
        j += 1
    if instrs[j].op != 0x2A:
        return kind + ', no globals'
    tail = [mnemonic(i) for i in instrs[j:j + (7 if cond else 5)]]
    want = (['SAVEBP', 'RSADDI', 'JSR', 'CPDOWNSP', 'MOVSP', 'RESTOREBP', 'MOVSP'] if cond else
            ['SAVEBP', 'JSR', 'RESTOREBP', 'MOVSP', 'RETN'])
    if tail != want:
        return f'{kind}, globals, unusual: ' + ' '.join(tail)
    return kind + ', globals'


def disassemble(data, names=None, raw=False):
    instrs = decode(data)
    errs = check_targets(instrs)
    labels = {}
    for i in instrs:
        if i.op == 0x1E:
            labels.setdefault(i.offset + i.args[0], f'sub_{i.offset + i.args[0]:08x}')
    for i in instrs:
        if i.op in (0x1D, 0x1F, 0x25):
            labels.setdefault(i.offset + i.args[0], f'loc_{i.offset + i.args[0]:08x}')
        elif i.op == 0x2C:
            labels.setdefault(i.offset + i.type, f'deferred_{i.offset + i.type:08x}')
    lines = [f'; NCS V1.0, {len(data)} bytes, {len(instrs)} instructions']
    for i in instrs:
        if i.offset in labels:
            lines.append(f'{labels[i.offset]}:')
        lines.append('    ' + format_instr(i, data if raw else None, names, labels))
    for e in errs:
        lines.append('; ERROR ' + e)
    return '\n'.join(lines), errs


# --- Stack-depth check -------------------------------------------------------------------------

CELL = 4


class StackError(Exception):
    pass


class Recursive(Exception):
    def __init__(self, target):
        super().__init__(f'{target:08x}: recursive call')
        self.target = target


def check_stack(instrs, sigs):
    """Walk the entry point, every subroutine (JSR target) and every STORE_STATE deferred block,
    tracking the stack depth in bytes relative to where each starts, and check that:
    - every path reaching an instruction arrives with the same depth,
    - ACTION pops exactly the cells its routine's first `argc` parameters take (vector 3,
      action 0, others 1) and pushes its return type's cells,
    - every RETN of a subroutine is at the same depth, which is the subroutine's net effect,
    - a deferred block returns at the depth it started (its saved locals) and never pops or
      copies from below them; the entry point never copies from below its start,
    - MOVSP only shrinks the stack, SP copies have a negative offset covering the size.
    `sigs` is a list of (return_cells, [param_cells...]) per routine index.

    One path refinement: BioWare's compiler emits `a || b` as
        a; CPTOPSP -4 4; JZ eval_b; CPTOPSP -4 4; JZ or; eval_b: b; or: LOGORII
    whose second JZ tests a copy of a value just found non-zero, so it is never taken (and its
    target would be one cell short). The walk tracks "top is a copy of the cell under it" and
    "top is known non-zero" to drop such edges.

    Returns (problems, info, globals, states): info counts subroutines, deferred blocks and
    pruned edges; globals lists the depth at each SAVEBP in the entry (the global variables'
    size); states lists each STORE_STATE's (bp_bytes, sp_bytes)."""
    by_off = {i.offset: k for k, i in enumerate(instrs)}
    net = {}          # subroutine start offset -> net depth change at RETN (bytes)
    in_progress = set()
    guess = {}        # recursive subroutine -> net effect assumed while verifying it
    cut = set()       # recursive subroutines whose net effect is being learned
    cut_memo = {}     # net effects found while learning (paths through `cut` skipped)
    problems = []
    info = Counter()
    states = []
    globals_size = []

    def walk(start, depth0, kind):
        """Over one routine body; returns the depth at RETN (None if it never returns)."""
        depth_at = {}
        visited = set()
        ret_depth = None
        work = [(start, depth0, False, False)]
        while work:
            off, d, nz, dup = work.pop()
            while True:
                if (off, nz, dup) in visited:
                    break
                visited.add((off, nz, dup))
                if depth_at.setdefault(off, d) != d:
                    raise StackError(f'{off:08x}: reached with depth {d} and {depth_at[off]}')
                k = by_off.get(off)
                if k is None:
                    raise StackError(f'{off:08x}: not an instruction')
                i = instrs[k]
                op, ty = i.op, i.type
                nxt = off + i.size
                nz2 = dup2 = False
                if op in (0x01, 0x03):           # CPDOWNSP / CPTOPSP
                    rel, n = i.args
                    if rel >= 0 or -rel < n:
                        raise StackError(f'{off:08x}: SP copy offset {rel} size {n}')
                    if kind != 'sub' and -rel > d:
                        raise StackError(f'{off:08x}: {kind} copies from below its start')
                    if op == 0x03:
                        d += n
                        if rel == -4 and n == 4:
                            nz2, dup2 = nz, True
                elif op in (0x02, 0x04):         # RSADD, CONST
                    d += CELL
                elif op == 0x05:
                    rid, argc = i.args
                    if rid >= len(sigs):
                        raise StackError(f'{off:08x}: routine {rid} out of range')
                    ret, params = sigs[rid]
                    if argc > len(params):
                        raise StackError(f'{off:08x}: routine {rid} called with {argc} args, has {len(params)}')
                    d -= CELL * sum(params[:argc])
                    d += CELL * ret
                elif op in (0x06, 0x07, 0x08, 0x09, 0x0A, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12,
                            0x13, 0x18):
                    d -= CELL
                elif op in (0x0B, 0x0C):
                    d -= (2 * i.args[0] - CELL) if ty == 0x24 else CELL
                elif op in (0x14, 0x15, 0x16, 0x17):
                    d -= (3 if ty == 0x3A else 1) * CELL
                elif op in (0x19, 0x1A, 0x22, 0x23, 0x24, 0x28, 0x29, 0x2D):
                    pass
                elif op == 0x1B:
                    if i.args[0] > 0:
                        raise StackError(f'{off:08x}: MOVSP {i.args[0]} grows the stack')
                    d += i.args[0]
                elif op == 0x1D:
                    off = off + i.args[0]
                    nz = dup = False
                    continue
                elif op == 0x1E:
                    t = off + i.args[0]
                    if t in cut and t not in net and t not in guess:
                        break                 # learning t's net effect: skip recursive paths
                    n = sub_net(t)
                    if n is None:             # only while learning: every path of t recursed
                        break
                    d += n
                elif op in (0x1F, 0x25):         # JZ / JNZ pop the tested cell
                    d -= CELL
                    taken = off + i.args[0]
                    if op == 0x1F:
                        if nz:
                            info['pruned'] += 1
                        else:
                            work.append((taken, d, False, False))
                        nz2 = dup             # fell through: the tested value was non-zero
                    else:
                        work.append((taken, d, dup, False))
                        if nz:
                            info['pruned'] += 1
                            break
                elif op == 0x20:
                    if ret_depth is not None and ret_depth != d:
                        raise StackError(f'{off:08x}: RETN at depth {d}, earlier RETN at {ret_depth}')
                    ret_depth = d
                    break
                elif op == 0x21:
                    size, keep_off, keep_size = i.args
                    if keep_off < 0 or keep_off + keep_size > size or (size > d and kind != 'sub'):
                        raise StackError(f'{off:08x}: DESTRUCT {size} {keep_off} {keep_size}')
                    d -= size - keep_size
                elif op in (0x26, 0x27):
                    if op == 0x27:
                        d += i.args[1]
                elif op == 0x2A:
                    globals_size.append(d)
                    d += CELL
                elif op == 0x2B:
                    d -= CELL
                elif op == 0x2C:
                    bp_bytes, sp_bytes = i.args
                    states.append((bp_bytes, sp_bytes))
                    # The deferred block runs later, on a stack holding only the saved locals.
                    info['deferred'] += 1
                    if sp_bytes > d and kind != 'sub':
                        raise StackError(f'{off:08x}: STORE_STATE saves {sp_bytes} of {d} bytes')
                    r = walk(off + ty, sp_bytes, 'deferred')
                    if r is not None and r != sp_bytes:
                        raise StackError(f'{off:08x}: deferred block returns at {r}, saved {sp_bytes}')
                else:
                    raise StackError(f'{off:08x}: unhandled {mnemonic(i)}')
                if d < 0 and kind != 'sub':
                    raise StackError(f'{off:08x}: {kind} pops below its start')
                off, nz, dup = nxt, nz2, dup2
        return ret_depth

    def sub_net(t):
        if t in net:
            return net[t]
        if cut and t in cut_memo:
            return cut_memo[t]
        if t in in_progress:
            if t in guess:
                return guess[t]
            raise Recursive(t)
        in_progress.add(t)
        try:
            r = walk(t, 0, 'sub')
        except Recursive as ex:
            if ex.target != t:
                raise
            # A recursive subroutine: learn its net effect from the paths that return without
            # recursing, then walk it again using that value at the recursive calls.
            info['recursive'] += 1
            cut.add(t)
            try:
                r0 = walk(t, 0, 'sub')
            finally:
                cut.discard(t)
            if r0 is None:
                raise StackError(f'{t:08x}: recursive subroutine has no non-recursive return')
            cut_memo.clear()
            guess[t] = r0
            try:
                r = walk(t, 0, 'sub')
            finally:
                del guess[t]
            if r != r0:
                raise StackError(f'{t:08x}: recursive subroutine returns at {r} and {r0}')
        finally:
            in_progress.discard(t)
        if cut:
            # Learning a recursive subroutine's net effect: this result may come from a subset
            # of paths, so it is not kept beyond that.
            cut_memo[t] = r
            return r
        if r is None:
            raise StackError(f'{t:08x}: subroutine never returns')
        net[t] = r
        info['subroutines'] += 1
        return r

    try:
        r = walk(instrs[0].offset, 0, 'entry')
        info['entry_net'] = r if r is not None else 0
    except (StackError, Recursive) as e:
        problems.append(str(e))
    return problems, info, globals_size, states


# --- Corpus ------------------------------------------------------------------------------------

def every_ncs():
    import kres
    g = kres.Game()
    return g, g.every_entry('ncs')


def read_entries(entries):
    """Yield (entry, bytes), opening each container once."""
    by_cont = defaultdict(list)
    for e in entries:
        by_cont[e.container].append(e)
    for cont in sorted(by_cont):
        with open(cont, 'rb') as f:
            for e in sorted(by_cont[cont], key=lambda e: e.offset):
                f.seek(e.offset)
                yield e, f.read(e.size)


def stack_signatures():
    import nwscript
    sigs = []
    for r in nwscript.load_routines():
        sigs.append((nwscript.cells(r.ret), [nwscript.cells(p.type) for p in r.params]))
    return sigs


def corpus(out_path, do_stack=True):
    g, entries = every_ncs()
    sigs = stack_signatures() if do_stack else None
    names = routine_names()
    files = 0
    failures = []
    stack_fail = []
    stack_info = Counter()
    contents = {}                       # sha1 -> first (resref, container)
    resref_content = set()              # (resref, sha1)
    op_count = Counter()                # (op, type) -> instructions, over every copy
    op_unique = Counter()               # (op, type) -> instructions, over unique contents
    op_files = Counter()                # (op, type) -> unique contents using it
    action_files = defaultdict(set)     # routine -> {(resref, sha1)}
    action_sites = Counter()            # routine -> call sites over unique (resref, sha1)
    action_argc = defaultdict(Counter)  # routine -> argc -> sites
    const_obj = Counter()
    store_state_type = Counter()
    sizes = []
    stack_checked = 0
    layouts = Counter()                 # entry code up to the first RETN, unique contents
    globals_vs_state = Counter()        # STORE_STATE bp_bytes == globals size?
    state_sizes = Counter()
    stack_known = []
    shapes = Counter()                  # deferred block bodies, collapsed
    consumers = Counter()               # routine taking the action argument after STORE_STATE
    for e, data in read_entries(entries):
        files += 1
        where = f'{e.resref}.ncs in {os.path.relpath(e.container, g.dir)}'
        try:
            instrs = decode(data)
        except NcsError as ex:
            failures.append(f'{where}: {ex}')
            continue
        errs = check_targets(instrs)
        if errs:
            failures.append(f'{where}: ' + '; '.join(errs[:3]))
            continue
        h = hashlib.sha1(data).hexdigest()
        key = (e.resref, h)
        for i in instrs:
            op_count[(i.op, i.type)] += 1
        new_content = h not in contents
        if new_content:
            contents[h] = where
            sizes.append(len(data))
            seen = set()
            for i in instrs:
                op_unique[(i.op, i.type)] += 1
                seen.add((i.op, i.type))
                if i.op == 0x04 and i.type == 0x06:
                    const_obj[i.args[0]] += 1
                elif i.op == 0x2C:
                    store_state_type[i.type] += 1
            for s in seen:
                op_files[s] += 1
            layouts[program_layout(instrs)] += 1
            if do_stack:
                stack_checked += 1
                probs, info, gl, states = check_stack(instrs, sigs)
                stack_info.update(info)
                if probs and e.resref in KNOWN_STACK:
                    stack_known.append(f'{where}: ' + '; '.join(probs[:2]) +
                                       f'\n        explained: {KNOWN_STACK[e.resref]}')
                elif probs:
                    stack_fail.append(f'{where}: ' + '; '.join(probs[:2]))
                deferred_shapes(instrs, shapes, consumers)
                gsize = gl[0] if gl else 0
                for bp, sp in states:
                    globals_vs_state['bp_bytes == globals size' if bp == gsize else
                                     f'bp_bytes {bp} vs globals {gsize}'] += 1
                    state_sizes[(bp, sp)] += 1
        if key not in resref_content:
            resref_content.add(key)
            for i in instrs:
                if i.op == 0x05:
                    action_files[i.args[0]].add(key)
                    action_sites[i.args[0]] += 1
                    action_argc[i.args[0]][i.args[1]] += 1

    out = []
    w = out.append
    w('NCS corpus statistics (ncsdis.py --corpus)')
    w('')
    w(f'NCS copies decoded:            {files}')
    w(f'Unique contents (sha1):        {len(contents)}')
    w(f'Unique (resref, content):      {len(resref_content)}')
    w(f'Distinct resrefs:              {len({k[0] for k in resref_content})}')
    w(f'Decode/validation failures:    {len(failures)}')
    for f in failures:
        w('  FAIL ' + f)
    if do_stack:
        w(f'Stack-depth check (unique):    {stack_checked} checked, {len(stack_fail)} unexplained failures; '
          f'{stack_info["subroutines"]} subroutine walks, {stack_info["deferred"]} deferred-block walks, '
          f'{stack_info["pruned"]} never-taken `||` branches pruned, '
          f'{stack_info["recursive"]} recursive subroutines')
        for f in stack_fail:
            w('  STACK ' + f)
        w(f'Explained stack-check failures: {len(stack_known)}')
        for f in stack_known:
            w('  KNOWN ' + f)
    if sizes:
        sizes.sort()
        w(f'Unique sizes: min {sizes[0]}, median {sizes[len(sizes) // 2]}, max {sizes[-1]} bytes')
    w('')
    w('Opcode/type usage: instructions over every copy, over unique contents, unique files using it')
    for (op, ty) in sorted(set(op_count) | {(op, t) for op, ts in ALLOWED.items() for t in ts}):
        w(f'  0x{op:02x} 0x{ty:02x}  {mnemonic(Instr(0, op, ty, (), 0)):<18} {op_count[(op, ty)]:>9} '
          f'{op_unique[(op, ty)]:>9} {op_files[(op, ty)]:>7}')
    w('')
    w('CONST object operands (unique contents):')
    for k, n in const_obj.most_common():
        w(f'  {k:>12}  {n}')
    w('')
    w('STORE_STATE type bytes (unique contents):')
    for k, n in store_state_type.most_common():
        w(f'  0x{k:02x}  {n}')
    if do_stack:
        w('STORE_STATE first operand against the globals size (depth at SAVEBP):')
        for k, n in globals_vs_state.most_common(20):
            w(f'  {n:>6}  {k}')
        w('STORE_STATE (bp_bytes, sp_bytes), most common:')
        for k, n in state_sizes.most_common(12):
            w(f'  {n:>6}  {k}')
        w('Routine taking the action argument (first ACTION with an action parameter after the')
        w("STORE_STATE's JMP target, straight-line):")
        for k, n in consumers.most_common():
            w(f'  {n:>6}  {k}')
        w('Deferred block bodies (resume point to RETN, collapsed), most common:')
        for k, n in shapes.most_common(15):
            w(f'  {n:>6}  {k}')
    w('')
    w('Program layouts (unique contents; see program_layout):')
    for k, n in layouts.most_common(20):
        w(f'  {n:>6}  {k}')
    w('')
    total_sites = sum(action_sites.values())
    w(f'ACTION routines used: {len(action_sites)}; call sites {total_sites} '
      f'(over unique (resref, content)); max routine index {max(action_sites) if action_sites else None}')
    w('routine  files  sites  argc-counts  name')
    for rid in sorted(action_sites, key=lambda r: (-len(action_files[r]), r)):
        argc = ','.join(f'{a}:{n}' for a, n in sorted(action_argc[rid].items()))
        n = names[rid] if names and rid < len(names) else ''
        w(f'  {rid:>5} {len(action_files[rid]):>6} {action_sites[rid]:>6}  {argc:<12} {n}')
    text = '\n'.join(out) + '\n'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(text)
    return text, failures, stack_fail, {
        'action_files': action_files, 'action_sites': action_sites, 'action_argc': action_argc,
    }


def action_usage():
    """Per routine: (files, sites, argc Counter), over unique (resref, content) NCS files.
    Decodes the whole corpus (no stack check)."""
    g, entries = every_ncs()
    seen = set()
    files = defaultdict(set)
    sites = Counter()
    argc = defaultdict(Counter)
    for e, data in read_entries(entries):
        h = hashlib.sha1(data).hexdigest()
        key = (e.resref, h)
        if key in seen:
            continue
        seen.add(key)
        for i in decode(data):
            if i.op == 0x05:
                files[i.args[0]].add(key)
                sites[i.args[0]] += 1
                argc[i.args[0]][i.args[1]] += 1
    return {r: (len(files[r]), sites[r], argc[r]) for r in sites}, len(seen)


def load(arg):
    if os.path.isfile(arg):
        with open(arg, 'rb') as f:
            return f.read()
    import kres
    resref = arg[:-4] if arg.lower().endswith('.ncs') else arg
    data = kres.Game().get(resref, 'ncs')
    if data is None:
        raise SystemExit(f'{arg}: no such file or NCS resource')
    return data


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    if '--corpus' in argv:
        out = argv[argv.index('-o') + 1] if '-o' in argv else DEFAULT_STATS
        text, failures, stack_fail, _ = corpus(out, do_stack='--no-stack' not in argv)
        print(text)
        print(f'(written to {out})')
        return 1 if failures or stack_fail else 0

    raw = '-x' in argv
    names = None if '--no-names' in argv else routine_names()
    path = [a for a in argv if not a.startswith('-')][0]
    data = load(path)
    try:
        text, errs = disassemble(data, names, raw)
    except NcsError as ex:
        print(f'{path}: {ex}', file=sys.stderr)
        return 1
    print(text)
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
