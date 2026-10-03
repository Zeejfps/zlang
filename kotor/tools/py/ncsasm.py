"""A small NCS assembler, for hand-written test and benchmark scripts (exploration only).

    a = Asm()
    a.op('CONSTI', 2); a.op('CONSTI', 3); a.op('ADDII'); a.op('RETN')
    data = a.bytes()                       # a whole NCS file

Mnemonics are ncsdis.py's (opcode stem plus type suffix). Operands follow the instruction:
CPDOWNSP/CPTOPSP/CPDOWNBP/CPTOPBP offset size; CONSTI/CONSTO int; CONSTF float; CONSTS str;
ACTION routine argc; MOVSP/INCISP/DECISP/INCIBP/DECIBP offset; EQUALTT/NEQUALTT size; DESTRUCT
size keep_offset keep_size; STORE_STATE globals frame (its type byte is always 0x10); JMP, JSR,
JZ and JNZ take a label name, defined with a.label(name).
"""

import struct

import ncsdis

_BY_NAME = {}
for _op, _stem in ncsdis.OPS.items():
    if _op == 0x2C:
        _BY_NAME['STORE_STATE'] = (_op, 0x10)
        continue
    for _ty in ncsdis.ALLOWED.get(_op, ()):
        _BY_NAME[_stem + ncsdis.TYPES[_ty]] = (_op, _ty)


class Asm:
    def __init__(self):
        self.code = bytearray()
        self.labels = {}
        self.fixups = []            # (position of the i32, instruction start, label)

    def at(self):
        return 13 + len(self.code)

    def label(self, name):
        self.labels[name] = self.at()

    def raw(self, b):
        self.code += bytes(b)

    def op(self, name, *args):
        op, ty = _BY_NAME[name]
        start = self.at()
        self.code += bytes([op, ty])
        if op in (0x01, 0x03, 0x26, 0x27):
            self.code += struct.pack('>iH', *args)
        elif op == 0x04:
            if ty == 0x05:
                b = args[0].encode('latin-1') if isinstance(args[0], str) else args[0]
                self.code += struct.pack('>H', len(b)) + b
            elif ty == 0x04:
                self.code += struct.pack('>f', args[0])
            else:
                self.code += struct.pack('>i', args[0])
        elif op == 0x05:
            self.code += struct.pack('>HB', *args)
        elif op in (0x0B, 0x0C) and ty == 0x24:
            self.code += struct.pack('>H', *args)
        elif op in (0x1B, 0x23, 0x24, 0x28, 0x29):
            self.code += struct.pack('>i', *args)
        elif op in ncsdis.JUMPS:
            self.fixups.append((len(self.code), start, args[0]))
            self.code += b'\0\0\0\0'
        elif op == 0x21:
            self.code += struct.pack('>HhH', *args)
        elif op == 0x2C:
            self.code += struct.pack('>ii', *args)
        elif args:
            raise ValueError(f'{name} takes no operands')

    def bytes(self):
        for pos, start, name in self.fixups:
            struct.pack_into('>i', self.code, pos, self.labels[name] - start)
        return b'NCS V1.0B' + struct.pack('>I', 13 + len(self.code)) + bytes(self.code)
