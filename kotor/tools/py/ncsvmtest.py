"""The VM's semantic tests: hand-assembled NCS programs, each with the result KOTOR's VM gives
(docs/re/vm.md), run by ncsrun on the stub engine and checked.

    python kotor/tools/py/ncsvmtest.py          writes kotor/out/ncsvmtest/*.ncs, runs ncsrun
                                                --results over them, prints failures; exit 1 if any

Each program starts at the first instruction with an empty stack and ends with RETN: a run that
leaves one int returns it ("ok N"), one that leaves nothing returns none ("ok none"), and a
fault names its kind (nwvm::kind_id). Programs that hand an action to DelayCommand also expect
the action's run to end normally; their deferred code checks what it was given and executes a
NOP (an invalid opcode) if anything is wrong.
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KOTOR = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(KOTOR)
sys.path.insert(0, HERE)

from ncsasm import Asm  # noqa: E402
import nwscript  # noqa: E402

OUT = os.path.join(KOTOR, 'out', 'ncsvmtest')
INT_MIN = -2147483648
INT_MAX = 2147483647

TESTS = []
_routines = None


def routine(name):
    global _routines
    if _routines is None:
        _routines = {r.name: r.index for r in nwscript.load_routines()}
    return _routines[name]


def test(name, expect, *code, actions=0):
    """code: (mnemonic, operands...) tuples, ('label', name), or ('raw', bytes)."""
    TESTS.append((name, expect, code, actions))


def ints(name, expect, *code):
    test(name, ('ok', expect), *code, ('RETN',))


def is_float(value, *code):
    """Code leaving a float, then a check that it is exactly `value`: leaves 1 or 0."""
    return code + (('CONSTF', value), ('EQUALFF',))


def build(code):
    a = Asm()
    for c in code:
        if c[0] == 'label':
            a.label(c[1])
        elif c[0] == 'raw':
            a.raw(c[1])
        else:
            a.op(*c)
    return a.bytes()


# ---- integers
ints('consti', 42, ('CONSTI', 42))
ints('addii', 5, ('CONSTI', 2), ('CONSTI', 3), ('ADDII',))
ints('subii', -1, ('CONSTI', 2), ('CONSTI', 3), ('SUBII',))
ints('addii_wraps', INT_MIN, ('CONSTI', INT_MAX), ('CONSTI', 1), ('ADDII',))
ints('mulii_wraps', -2, ('CONSTI', INT_MAX), ('CONSTI', 2), ('MULII',))
ints('divii', 3, ('CONSTI', 7), ('CONSTI', 2), ('DIVII',))
ints('divii_toward_zero', -3, ('CONSTI', -7), ('CONSTI', 2), ('DIVII',))
ints('modii', -1, ('CONSTI', -7), ('CONSTI', 2), ('MODII',))
ints('modii_sign', 1, ('CONSTI', 7), ('CONSTI', -2), ('MODII',))
test('divii_zero', ('fault', 'div_zero'), ('CONSTI', 1), ('CONSTI', 0), ('DIVII',), ('RETN',))
test('modii_zero', ('fault', 'div_zero'), ('CONSTI', 1), ('CONSTI', 0), ('MODII',), ('RETN',))
test('divii_overflow', ('fault', 'div_overflow'), ('CONSTI', INT_MIN), ('CONSTI', -1), ('DIVII',), ('RETN',))
test('modii_overflow', ('fault', 'div_overflow'), ('CONSTI', INT_MIN), ('CONSTI', -1), ('MODII',), ('RETN',))
ints('logand', 1, ('CONSTI', 2), ('CONSTI', 3), ('LOGANDII',))
ints('logand_zero', 0, ('CONSTI', 2), ('CONSTI', 0), ('LOGANDII',))
ints('logor', 1, ('CONSTI', 0), ('CONSTI', 5), ('LOGORII',))
ints('logor_zero', 0, ('CONSTI', 0), ('CONSTI', 0), ('LOGORII',))
ints('incor', 65, ('CONSTI', 1), ('CONSTI', 64), ('INCORII',))
ints('excor', 5, ('CONSTI', 6), ('CONSTI', 3), ('EXCORII',))
ints('booland', 2, ('CONSTI', 6), ('CONSTI', 3), ('BOOLANDII',))
ints('not_zero', 1, ('CONSTI', 0), ('NOTI',))
ints('not_five', 0, ('CONSTI', 5), ('NOTI',))
ints('compi', -1, ('CONSTI', 0), ('COMPI',))
ints('negi', -5, ('CONSTI', 5), ('NEGI',))
ints('negi_min', INT_MIN, ('CONSTI', INT_MIN), ('NEGI',))
ints('shleft_masks_count', 2, ('CONSTI', 1), ('CONSTI', 33), ('SHLEFTII',))
ints('shright', 3, ('CONSTI', 7), ('CONSTI', 1), ('SHRIGHTII',))
ints('shright_toward_zero', -3, ('CONSTI', -7), ('CONSTI', 1), ('SHRIGHTII',))
ints('ushright_sign_extends', -4, ('CONSTI', -8), ('CONSTI', 1), ('USHRIGHTII',))
ints('ltii', 1, ('CONSTI', 3), ('CONSTI', 4), ('LTII',))
ints('leqii', 1, ('CONSTI', 4), ('CONSTI', 4), ('LEQII',))
ints('gtii', 1, ('CONSTI', 5), ('CONSTI', 4), ('GTII',))
ints('geqii', 0, ('CONSTI', 4), ('CONSTI', 5), ('GEQII',))
ints('equalii', 1, ('CONSTI', 3), ('CONSTI', 3), ('EQUALII',))
ints('nequalii', 0, ('CONSTI', 3), ('CONSTI', 3), ('NEQUALII',))
ints('equalii_on_floats_compares_bits', 1, ('CONSTF', 1.0), ('CONSTF', 1.0), ('EQUALII',))

# ---- floats
ints('addff', 1, *is_float(3.75, ('CONSTF', 1.5), ('CONSTF', 2.25), ('ADDFF',)))
ints('subff', 1, *is_float(-0.75, ('CONSTF', 1.5), ('CONSTF', 2.25), ('SUBFF',)))
ints('mulff', 1, *is_float(3.0, ('CONSTF', 1.5), ('CONSTF', 2.0), ('MULFF',)))
ints('divff', 1, *is_float(1.5, ('CONSTF', 3.0), ('CONSTF', 2.0), ('DIVFF',)))
test('divff_zero', ('fault', 'div_zero'), ('CONSTF', 1.0), ('CONSTF', 0.0), ('DIVFF',), ('RETN',))
ints('addif', 1, *is_float(3.5, ('CONSTI', 3), ('CONSTF', 0.5), ('ADDIF',)))
ints('addfi', 1, *is_float(3.5, ('CONSTF', 0.5), ('CONSTI', 3), ('ADDFI',)))
ints('subif', 1, *is_float(2.5, ('CONSTI', 3), ('CONSTF', 0.5), ('SUBIF',)))
ints('subfi', 1, *is_float(-2.5, ('CONSTF', 0.5), ('CONSTI', 3), ('SUBFI',)))
ints('mulif', 1, *is_float(1.5, ('CONSTI', 3), ('CONSTF', 0.5), ('MULIF',)))
ints('mulfi', 1, *is_float(1.5, ('CONSTF', 0.5), ('CONSTI', 3), ('MULFI',)))
ints('divif', 1, *is_float(6.0, ('CONSTI', 3), ('CONSTF', 0.5), ('DIVIF',)))
ints('divfi', 1, *is_float(1.5, ('CONSTF', 3.0), ('CONSTI', 2), ('DIVFI',)))
test('divfi_zero', ('fault', 'div_zero'), ('CONSTF', 3.0), ('CONSTI', 0), ('DIVFI',), ('RETN',))
ints('negf', 1, *is_float(-1.5, ('CONSTF', 1.5), ('NEGF',)))
ints('gtff', 1, ('CONSTF', 2.5), ('CONSTF', 1.0), ('GTFF',))
ints('ltff', 0, ('CONSTF', 2.5), ('CONSTF', 1.0), ('LTFF',))
ints('leqff', 1, ('CONSTF', 1.0), ('CONSTF', 1.0), ('LEQFF',))
ints('geqff', 0, ('CONSTF', 0.5), ('CONSTF', 1.0), ('GEQFF',))
ints('equalff_by_bits', 0, ('CONSTF', 0.0), ('CONSTF', -0.0), ('EQUALFF',))
ints('nequalff', 1, ('CONSTF', 0.0), ('CONSTF', -0.0), ('NEQUALFF',))

# ---- strings and objects
ints('equalss_ignores_case', 1, ('CONSTS', 'abc'), ('CONSTS', 'ABC'), ('EQUALSS',))
ints('nequalss', 1, ('CONSTS', 'a'), ('CONSTS', 'b'), ('NEQUALSS',))
ints('addss', 1, ('CONSTS', 'ab'), ('CONSTS', 'c'), ('ADDSS',), ('CONSTS', 'abc'), ('EQUALSS',))
ints('addss_empty', 1, ('CONSTS', ''), ('CONSTS', 'c'), ('ADDSS',), ('CONSTS', 'c'), ('EQUALSS',))
ints('rsadds_is_empty', 1, ('RSADDS',), ('CONSTS', ''), ('EQUALSS',))
ints('consts_ends_at_nul', 1, ('CONSTS', 'ab\0cd'), ('CONSTS', 'ab'), ('EQUALSS',))
ints('object_self_is_valid', 1, ('CONSTO', 0), ('CONSTO', 1), ('NEQUALOO',))
ints('rsaddo_is_invalid', 1, ('RSADDO',), ('CONSTO', 1), ('EQUALOO',))
ints('consto_other_is_invalid', 1, ('CONSTO', 7), ('CONSTO', 1), ('EQUALOO',))
ints('intostring', 1, ('CONSTI', 42), ('ACTION', routine('IntToString'), 1), ('CONSTS', '42'), ('EQUALSS',))
ints('getstringlength', 5, ('CONSTS', 'hello'), ('ACTION', routine('GetStringLength'), 1))
test('strings_full', ('fault', 'strings_full'),
     ('CONSTS', 'x'), ('label', 'l'), ('CPTOPSP', -4, 4), ('CPTOPSP', -8, 4), ('ADDSS',),
     ('CPDOWNSP', -8, 4), ('MOVSP', -4), ('JMP', 'l'))
# Slots of strings no cell holds are used again, so this runs until the budget, not out of slots.
test('string_slots_reused', ('fault', 'budget'),
     ('label', 'l'), ('CONSTS', 'a'), ('MOVSP', -4), ('JMP', 'l'))

# ---- engine values
ints('engine_values_compare', 0, ('CONSTI', 1), ('ACTION', routine('EffectHeal'), 1),
     ('CONSTI', 1), ('ACTION', routine('EffectHeal'), 1), ('EQUALEFFECTEFFECT',))
ints('engine_value_copy_equal', 1, ('CONSTI', 1), ('ACTION', routine('EffectHeal'), 1),
     ('CPTOPSP', -4, 4), ('EQUALEFFECTEFFECT',))
ints('rsadd_engine_defaults_equal', 1, ('RSADDLOCATION',), ('RSADDLOCATION',), ('EQUALLOCLOC',))
ints('nequal_locations', 1, ('CONSTO', 0), ('ACTION', routine('GetLocation'), 1),
     ('CONSTO', 0), ('ACTION', routine('GetLocation'), 1), ('NEQUALLOCLOC',))

# ---- vectors and structures
VEC123 = (('CONSTF', 1.0), ('CONSTF', 2.0), ('CONSTF', 3.0))
VEC456 = (('CONSTF', 4.0), ('CONSTF', 5.0), ('CONSTF', 6.0))
VEC246 = (('CONSTF', 2.0), ('CONSTF', 4.0), ('CONSTF', 6.0))
ints('addvv', 1, *VEC123, *VEC456, ('ADDVV',), ('CONSTF', 5.0), ('CONSTF', 7.0), ('CONSTF', 9.0), ('EQUALTT', 12))
ints('subvv', 1, *VEC456, *VEC123, ('SUBVV',), ('CONSTF', 3.0), ('CONSTF', 3.0), ('CONSTF', 3.0), ('EQUALTT', 12))
ints('mulvf', 1, *VEC123, ('CONSTF', 2.0), ('MULVF',), *VEC246, ('EQUALTT', 12))
ints('mulfv', 1, ('CONSTF', 2.0), *VEC123, ('MULFV',), *VEC246, ('EQUALTT', 12))
ints('divvf', 1, *VEC246, ('CONSTF', 2.0), ('DIVVF',), *VEC123, ('EQUALTT', 12))
test('divvf_zero', ('fault', 'div_zero'), *VEC246, ('CONSTF', 0.0), ('DIVVF',), ('RETN',))
ints('nequaltt', 1, *VEC123, *VEC246, ('NEQUALTT', 12))
test('equaltt_mixed_types', ('fault', 'not_comparable'),
     ('CONSTI', 1), ('CONSTF', 1.0), ('CONSTI', 1), ('CONSTI', 1), ('EQUALTT', 8), ('RETN',))
ints('destruct_middle', 2, ('CONSTI', 1), ('CONSTI', 2), ('CONSTI', 3), ('DESTRUCT', 12, 4, 4))
ints('destruct_last', 3, ('CONSTI', 1), ('CONSTI', 2), ('CONSTI', 3), ('DESTRUCT', 12, 8, 4))

# ---- the stack
ints('cpdownsp', 2, ('CONSTI', 1), ('CONSTI', 2), ('CPDOWNSP', -8, 4), ('MOVSP', -4))
ints('cptopsp', 14, ('CONSTI', 7), ('CPTOPSP', -4, 4), ('ADDII',))
ints('movsp', 1, ('CONSTI', 1), ('CONSTI', 2), ('MOVSP', -4))
ints('incisp_decisp', 6, ('CONSTI', 5), ('INCISPI', -4), ('INCISPI', -4), ('DECISPI', -4))
ints('globals_through_bp', 51,
     ('CONSTI', 10), ('CONSTI', 20), ('SAVEBP',),
     ('CPTOPBP', -8, 4), ('CPTOPBP', -4, 4), ('ADDII',), ('CPDOWNBP', -8, 4), ('MOVSP', -4),
     ('INCIBPI', -4), ('INCIBPI', -4), ('DECIBPI', -4), ('RESTOREBP',), ('ADDII',))
test('restorebp_wrong_type', ('fault', 'wrong_type'), ('CONSTF', 1.0), ('RESTOREBP',), ('RETN',))
test('cptopsp_outside', ('fault', 'bad_offset'), ('CONSTI', 1), ('CPTOPSP', -8, 4), ('RETN',))
test('cpdownsp_outside', ('fault', 'bad_offset'), ('CONSTI', 1), ('CPDOWNSP', -8, 4), ('RETN',))
test('stack_full', ('fault', 'stack_full'), ('label', 'l'), ('CONSTI', 1), ('CONSTI', 1), ('CONSTI', 1), ('JMP', 'l'))
test('underflow', ('fault', 'underflow'), ('ADDII',), ('RETN',))
test('movsp_underflow', ('fault', 'underflow'), ('MOVSP', -4), ('RETN',))
test('wrong_type', ('fault', 'wrong_type'), ('CONSTF', 1.0), ('CONSTI', 1), ('ADDII',), ('RETN',))
test('jz_wrong_type', ('fault', 'wrong_type'), ('CONSTF', 0.0), ('JZ', 'l'), ('label', 'l'), ('RETN',))

# ---- control flow and the run
ints('jz_taken', 2, ('CONSTI', 0), ('JZ', 'two'), ('CONSTI', 1), ('RETN',), ('label', 'two'), ('CONSTI', 2))
ints('jnz_taken', 2, ('CONSTI', 3), ('JNZ', 'two'), ('CONSTI', 1), ('RETN',), ('label', 'two'), ('CONSTI', 2))
# int fact(int n) { return n <= 1 ? 1 : n * fact(n - 1); } with fact(5) as the result.
ints('recursion', 120,
     ('RSADDI',), ('CONSTI', 5), ('JSR', 'fact'), ('RETN',),
     ('label', 'fact'),
     ('CPTOPSP', -4, 4), ('CONSTI', 1), ('LEQII',), ('JZ', 'rec'),
     ('CONSTI', 1), ('CPDOWNSP', -12, 4), ('MOVSP', -4), ('MOVSP', -4), ('RETN',),
     ('label', 'rec'),
     ('RSADDI',), ('CPTOPSP', -8, 4), ('CONSTI', 1), ('SUBII',), ('JSR', 'fact'),
     ('CPTOPSP', -8, 4), ('MULII',), ('CPDOWNSP', -12, 4), ('MOVSP', -8))
test('call_depth', ('fault', 'call_depth'), ('label', 'f'), ('JSR', 'f'), ('RETN',))
test('budget', ('fault', 'budget'), ('label', 'l'), ('JMP', 'l'))
test('nop_is_invalid', ('fault', 'invalid_opcode'), ('raw', b'\x2d\x00'), ('RETN',))
test('past_end', ('fault', 'past_end'), ('CONSTI', 1))
test('void_script', ('ok', 'none'), ('RETN',))
test('one_string_left', ('ok', 'none'), ('CONSTS', 'x'), ('RETN',))
test('unbalanced', ('fault', 'unbalanced'), ('CONSTI', 1), ('CONSTI', 2), ('RETN',))
test('routine_wrong_argument', ('fault', 'wrong_type'), ('CONSTF', 1.0), ('ACTION', routine('Random'), 1), ('RETN',))
test('action_without_store_state', ('fault', 'no_state'), ('CONSTF', 1.0), ('ACTION', routine('DelayCommand'), 2), ('RETN',))

# ---- actions: STORE_STATE, then DelayCommand takes the code after it
DELAY = routine('DelayCommand')
CHECK_FAIL = (('label', 'bad'), ('raw', b'\x2d\x00'))
# A local saved in the frame: the action sees 7 at the top.
test('action_frame', ('ok', 7),
     ('CONSTI', 7),
     ('STORE_STATE', 0, 4), ('JMP', 'after'),
     ('CPTOPSP', -4, 4), ('CONSTI', 7), ('EQUALII',), ('JZ', 'bad'), ('RETN',),
     ('label', 'after'), ('CONSTF', 1.0), ('ACTION', DELAY, 2), ('RETN',), *CHECK_FAIL, actions=1)
# A global (below BP) and a local: the action finds both where the bytecode expects them.
test('action_globals', ('ok', 'none'),
     ('CONSTI', 3), ('SAVEBP',), ('CONSTI', 9), ('CONSTS', 'hi'),
     ('STORE_STATE', 4, 8), ('JMP', 'after'),
     ('CPTOPBP', -4, 4), ('CONSTI', 3), ('EQUALII',), ('JZ', 'bad'),
     ('CPTOPSP', -8, 4), ('CONSTI', 9), ('EQUALII',), ('JZ', 'bad'),
     ('CPTOPSP', -4, 4), ('CONSTS', 'HI'), ('EQUALSS',), ('JZ', 'bad'), ('RETN',),
     ('label', 'after'), ('CONSTF', 1.0), ('ACTION', DELAY, 2),
     ('MOVSP', -8), ('RESTOREBP',), ('MOVSP', -4), ('RETN',), *CHECK_FAIL, actions=1)
# Both sizes 0 keep the whole stack.
test('action_whole_stack', ('ok', 5),
     ('CONSTI', 5),
     ('STORE_STATE', 0, 0), ('JMP', 'after'),
     ('CPTOPSP', -4, 4), ('CONSTI', 5), ('EQUALII',), ('JZ', 'bad'), ('RETN',),
     ('label', 'after'), ('CONSTF', 1.0), ('ACTION', DELAY, 2), ('RETN',), *CHECK_FAIL, actions=1)
# An action that hands on another: both run.
test('action_nested', ('ok', 'none'),
     ('STORE_STATE', 0, 0), ('JMP', 'after'),
     ('STORE_STATE', 0, 0), ('JMP', 'inner'), ('RETN',),
     ('label', 'inner'), ('CONSTF', 1.0), ('ACTION', DELAY, 2), ('RETN',),
     ('label', 'after'), ('CONSTF', 1.0), ('ACTION', DELAY, 2), ('RETN',), actions=2)


def main(argv):
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    want = {}
    for name, expect, code, actions in TESTS:
        with open(os.path.join(OUT, name + '.ncs'), 'wb') as f:
            f.write(build(code))
        want[name] = (expect, actions)
    cmd = ['bash', 'kotor/tools/ctxc', 'run', 'kotor/tools/ncsrun', '--',
           os.path.relpath(OUT, ROOT).replace(os.sep, '/'), '--results', '--show', '0']
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    got = {}
    for line in p.stdout.splitlines():
        if line.startswith('RESULT\t'):
            _, name, what, status, value = line.split('\t')
            got.setdefault(name, []).append((what, status, value))
    failures = 0
    for name, (expect, actions) in want.items():
        runs = got.get(name)
        if not runs:
            print(f'FAIL {name}: no result')
            failures += 1
            continue
        script = runs[0]
        if (script[1], script[2]) != (expect[0], str(expect[1])):
            print(f'FAIL {name}: wanted {expect[0]} {expect[1]}, got {script[1]} {script[2]}')
            failures += 1
        acts = runs[1:]
        if len(acts) != actions or any(a[1] != 'ok' for a in acts):
            print(f'FAIL {name}: wanted {actions} actions ending normally, got {acts}')
            failures += 1
    print(f'{len(want)} tests, {failures} failures')
    if p.returncode not in (0, 1):
        print(p.stdout[-2000:], p.stderr[-2000:])
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
