"""Write a VM benchmark script, kotor/out/ncsbench.ncs: a loop of the instructions BioWare's
compiler emits most (local copies, constants, int and float arithmetic, compares, jumps, a
subroutine call), with no engine routines, so `ncsrun` times the VM alone:

    python kotor/tools/py/ncsbench.py [ITERATIONS]
    kotor/tools/ctxc run kotor/tools/ncsrun -- kotor/out/ncsbench.ncs --budget 4000000000

The script, as NWScript, compiled by hand the way BioWare's compiler lays code out:

    int add(int a, int b) { return a + b; }
    void main() {
        int i = 0; int s = 0; float f = 0.0;
        while (i < N) {
            s = add(s, i * 3);
            f = f + 1.5;
            if (s > 1000) { s = s - 1000; }
            i++;
        }
    }
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KOTOR = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from ncsasm import Asm  # noqa: E402


def program(n):
    a = Asm()
    a.op('JSR', 'main')
    a.op('RETN')
    a.label('main')
    for rs, const, v in (('RSADDI', 'CONSTI', 0), ('RSADDI', 'CONSTI', 0), ('RSADDF', 'CONSTF', 0.0)):
        a.op(rs)
        a.op(const, v)
        a.op('CPDOWNSP', -8, 4)
        a.op('MOVSP', -4)
    a.label('loop')                                 # locals: i -12, s -8, f -4
    a.op('CPTOPSP', -12, 4)
    a.op('CONSTI', n)
    a.op('LTII')
    a.op('JZ', 'end')
    a.op('RSADDI')                                  # add's result
    a.op('CPTOPSP', -16, 4)                         # i * 3, the second argument, pushed first
    a.op('CONSTI', 3)
    a.op('MULII')
    a.op('CPTOPSP', -16, 4)                         # s
    a.op('JSR', 'add')
    a.op('CPDOWNSP', -12, 4)                        # s = the result
    a.op('MOVSP', -4)
    a.op('CPTOPSP', -4, 4)                          # f = f + 1.5
    a.op('CONSTF', 1.5)
    a.op('ADDFF')
    a.op('CPDOWNSP', -8, 4)
    a.op('MOVSP', -4)
    a.op('CPTOPSP', -8, 4)                          # if (s > 1000)
    a.op('CONSTI', 1000)
    a.op('GTII')
    a.op('JZ', 'skip')
    a.op('CPTOPSP', -8, 4)
    a.op('CONSTI', 1000)
    a.op('SUBII')
    a.op('CPDOWNSP', -12, 4)
    a.op('MOVSP', -4)
    a.label('skip')
    a.op('INCISPI', -12)
    a.op('JMP', 'loop')
    a.label('end')
    a.op('MOVSP', -12)
    a.op('RETN')
    a.label('add')                                  # result -12, b -8, a -4
    a.op('CPTOPSP', -4, 4)
    a.op('CPTOPSP', -12, 4)
    a.op('ADDII')
    a.op('CPDOWNSP', -16, 4)
    a.op('MOVSP', -12)
    a.op('RETN')
    return a.bytes()


def main(argv):
    n = int(argv[0]) if argv else 1000000
    out = os.path.join(KOTOR, 'out', 'ncsbench.ncs')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'wb') as f:
        f.write(program(n))
    print(f'{out}: {n} iterations')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
