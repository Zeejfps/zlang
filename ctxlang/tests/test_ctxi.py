"""Tests for the ctxlang interpreter.  Run:  python -m unittest discover tests"""

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ctxi.__main__ import run_source  # noqa: E402
from ctxi.lexer import CompileError  # noqa: E402
from ctxi.runtime import Trap  # noqa: E402

with open(os.path.join(ROOT, 'examples', 'list.ctx'), encoding='utf-8') as f:
    LIST_SRC = f.read()
LIB = LIST_SRC[:LIST_SRC.index('fn main {')]

MAIN_SETUP = """
fn main { mut io: Io } {
    let mut mem: [4096]u8
    let mut heap = arena::Arena{ buf = slice::from{ ptr = &mem[0], len = mem.len }, used = 0 }
    let mut nums = list::new(i32){ realloc = arena::alloc }
    let mut total = 0
%s
}
"""


def run(src):
    out = io.StringIO()
    run_source(src, out=out)
    return out.getvalue()


class Base(unittest.TestCase):
    def assertOutput(self, src, expected):
        self.assertEqual(run(src), expected)

    def assertCompileError(self, src, fragment):
        with self.assertRaises(CompileError) as cm:
            run(src)
        self.assertIn(fragment, cm.exception.msg)

    def assertTrap(self, src, fragment):
        with self.assertRaises(Trap) as cm:
            run(src)
        self.assertIn(fragment, cm.exception.msg)


class ListExample(Base):
    def test_runs(self):
        self.assertOutput(LIST_SRC, '10\n20\n30\n40\n100\n10\n')

    def lib_error(self, body, fragment, extra=''):
        self.assertCompileError(LIB + extra + MAIN_SETUP % body, fragment)

    def test_setup_compiles(self):
        self.assertOutput(LIB + MAIN_SETUP % '    io::println_i64{ &io, n = total }', '0\n')

    def test_wrong_heap_type(self):
        self.lib_error("""
    let mut m = 1
    list::push{ list = &nums, heap = &m, item = 1 }""", 'expected')

    def test_fn_needs_more_context(self):
        self.lib_error('    list::each{ list = nums, f = print_item }', "needs `mut io`")

    def test_bound_into_unbound(self):
        self.lib_error('    let h = Handler{ f = print_item{ &io, _ } }',
                       'expected fn{ item: i32 }, got &fn{ item: i32 }',
                       'struct Handler { f: fn{ item: i32 } }\n')

    def test_bound_struct_field(self):
        self.lib_error('', '`&fn` can only be', 'struct Handler2 { f: &fn{ item: i32 } }\n')

    def test_bound_as_allocator(self):
        extra = ('fn log_to { mut log: Io, mut heap: arena::Arena, mem: alloc::Bytes, new: usize, '
                 'align: usize } -> ?alloc::Bytes { return null }\n')
        self.lib_error('    let l = list::new(i32){ realloc = log_to{ log = &io, _ } }', 'got &fn', extra)

    def test_not_exhaustive(self):
        self.lib_error("""
    let ev = Event::pop
    match (ev) { push{ value } => { } }""", "match isn't exhaustive: missing pop, clear")

    def test_optional_not_unwrapped(self):
        self.lib_error('    io::println_i64{ &io, n = list::get{ list = nums, i = 0 } }',
                       'expected i64, got ?i32')

    def test_two_mut_refs(self):
        extra = 'fn move_first(S) { mut from: list::List(i32, S), mut to: list::List(i32, S), mut heap: S } { }\n'
        self.lib_error('    move_first{ from = &nums, to = &nums, .. }', 'two mut references to `nums`', extra)

    def test_match_scrutinee_overlap(self):
        self.lib_error("""
    let mut ev = Event::push{ value = 1 }
    match (&ev) {
        push{ &value } => { ev = Event::pop; value = 2 }
        else           => { }
    }""", 'ev overlaps the match scrutinee; access it only through `value`')

    def test_match_scrutinee_binding_ok(self):
        self.assertOutput(LIB + MAIN_SETUP % """
    let mut ev = Event::push{ value = 1 }
    match (&ev) {
        push{ &value } => { value = 7 }
        else           => { }
    }
    match (ev) {
        push{ value } => { io::println_i64{ &io, n = value } }
        else          => { }
    }""", '7\n')

    def test_maybe_unassigned(self):
        self.lib_error("""
    let ev: Event
    if (total > 100) { ev = Event::clear }
    apply{ &nums, ev, .. }""", '`ev` may be read before it is assigned')

    def test_held_overlap(self):
        extra = 'fn sum_into { mut total: i32, f: &fn{ item: i32 } } { }\n'
        self.lib_error("""
    let f = add_to{ &total, _ }
    sum_into{ &total, f }""", '`total` overlaps a place held by `f`', extra)

    def test_escape_return(self):
        extra = """fn make_arena {} -> arena::Arena {
    let mut mem: [64]u8
    return arena::Arena{ buf = slice::from{ ptr = &mem[0], len = mem.len }, used = 0 }
}
"""
        self.lib_error('', 'returned value holds the address of local `mem`', extra)

    def test_mutable_not_narrowed(self):
        self.lib_error("""
    let mut maybe = list::get{ list = nums, i = 0 }
    if (maybe != null) { io::println_i64{ &io, n = maybe } }""", 'expected i64, got ?i32')

    def test_not_caught_wrong_instance(self):
        self.assertOutput(LIB + MAIN_SETUP % """
    let mut mem2: [256]u8
    let mut other = arena::Arena{ buf = slice::from{ ptr = &mem2[0], len = mem2.len }, used = 0 }
    list::push{ list = &nums, heap = &other, item = 1 }
    io::println_u64{ &io, n = nums.len }""", '1\n')


class Basics(Base):
    def test_arith_and_loops(self):
        self.assertOutput("""
fn fib { n: u64 } -> u64 {
    if (n < 2) { return n }
    return fib{ n = n - 1 } + fib{ n = n - 2 }
}
fn main { mut io: Io } {
    io::println_u64{ &io, n = fib{ n = 20 } }
    let mut i = 0
    let mut s: i64
    while (i < 10) { s = s + @as(i64, i); i = i + 1 }
    io::println_i64{ &io, n = s }
    io::println_i64{ &io, n = -7 / 2 }
    io::println_i64{ &io, n = -7 % 2 }
    io::println_f64{ &io, n = 1.5 * 2.0 }
    io::println_bool{ &io, n = 3 > 2 and not (1 == 2) }
}
""", '6765\n45\n-3\n-1\n3.0\n true\n'.replace(' ', ''))

    def test_overflow_traps(self):
        self.assertTrap("""
fn main { mut io: Io } {
    let mut x: u8 = 250
    while (true) { x = x + 1 }
}
""", 'integer overflow')

    def test_unsigned_underflow_traps(self):
        self.assertTrap("""
fn main { mut io: Io } {
    let a: usize = 1
    let b = a - 2
}
""", 'integer overflow')

    def test_div_zero_traps(self):
        self.assertTrap("""
fn d { a: i32, b: i32 } -> i32 { return a / b }
fn main { mut io: Io } { let x = d{ a = 1, b = 0 } }
""", 'division by zero')

    def test_bounds_trap(self):
        self.assertTrap("""
fn main { mut io: Io } {
    let a = [1, 2, 3]
    let mut i: usize = 3
    io::println_i64{ &io, n = a[i] }
}
""", 'out of bounds')

    def test_explicit_trap(self):
        self.assertTrap('fn main { mut io: Io } { @trap() }', '@trap()')

    def test_wrap_and_trunc(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let x: u8 = 250
    io::println_u64{ &io, n = @wrap_add(x, 10) }
    io::println_i64{ &io, n = @trunc(i8, 200) }
    io::println_i64{ &io, n = @as(i32, 3.9) }
    io::println_i64{ &io, n = @as(i32, -3.9) }
    io::println_f64{ &io, n = @as(f64, 7) }
}
""", '4\n-56\n3\n-3\n7.0\n')

    def test_as_traps(self):
        self.assertTrap("""
fn main { mut io: Io } { let x: i32 = 300; io::println_u64{ &io, n = @as(u8, x) } }
""", 'not representable')

    def test_literal_range(self):
        self.assertCompileError('fn main { mut io: Io } { let x: u8 = 300 }', 'does not fit in u8')

    def test_mixed_types(self):
        self.assertCompileError("""
fn main { mut io: Io } { let a: i32 = 1; let b: u32 = 2; let c = a + b }
""", 'incompatible types')

    def test_structs_and_pointers(self):
        self.assertOutput("""
struct P { x: i32, y: i32 }
fn bump { mut p: P } { p.x = p.x + 1; p.y = p.y * 2 }
fn sum { p: P } -> i32 { return p.x + p.y }
fn main { mut io: Io } {
    let mut a = P{ x = 1, y = 5 }
    let b = a                      // copy
    bump{ p = &a }
    let q = &a
    q.x = q.x + 100
    io::println_i64{ &io, n = sum{ p = a } }
    io::println_i64{ &io, n = sum{ p = b } }
    let mut arr = [P{ x = 1, y = 1 }; 3]
    arr[2].y = 9
    let pa = &arr
    io::println_i64{ &io, n = pa[2].y + @as(i32, pa.len) }
    let p0 = &arr[0]
    io::println_i64{ &io, n = (p0 + 2).*.y }
}
""", '112\n6\n12\n9\n')

    def test_read_only_assignment(self):
        self.assertCompileError("""
struct P { x: i32 }
fn f { p: P } { p.x = 1 }
fn main { mut io: Io } { }
""", 'not a mutable place')

    def test_mut_arg_needs_mutable_place(self):
        self.assertCompileError("""
fn f { mut x: i32 } { }
fn main { mut io: Io } { let y = 1; f{ x = &y } }
""", 'not a mutable place')

    def test_missing_field(self):
        self.assertCompileError("""
fn f { a: i32, b: i32 } { }
fn main { mut io: Io } { f{ a = 1 } }
""", 'missing `b`')

    def test_forward_missing(self):
        self.assertCompileError("""
fn f { a: i32 } { }
fn main { mut io: Io } { f{ .. } }
""", 'cannot supply `a`')

    def test_missing_return(self):
        self.assertCompileError("""
fn f { a: i32 } -> i32 { if (a > 0) { return 1 } }
fn main { mut io: Io } { }
""", 'must end every path')

    def test_assigned_twice(self):
        self.assertCompileError("""
fn main { mut io: Io } { let x: i32; x = 1; x = 2 }
""", 'more than once')

    def test_generic_union_and_optional(self):
        self.assertOutput("""
union Result(T) { ok{ value: T }, err{ code: i32 } }
fn half { n: i32 } -> Result(i32) {
    if (n % 2 != 0) { return Result::err{ code = n } }
    return Result::ok{ value = n / 2 }
}
fn show { mut io: Io, r: Result(i32) } {
    match (r) {
        ok{ value } => { io::println_i64{ &io, n = value } }
        err{ code } => { io::println_i64{ &io, n = -code } }
    }
}
fn first(T) { a: [3]T } -> ?T { return a[0] }
fn main { mut io: Io } {
    show{ &io, r = half{ n = 10 } }
    show{ &io, r = half{ n = 7 } }
    let f = first{ a = [4, 5, 6] }
    if (f == null) { } else { io::println_i64{ &io, n = f } }
    let none: ?i32 = null
    match (none) {
        null => { io::println_i64{ &io, n = 0 } }
        some{ value } => { io::println_i64{ &io, n = value } }
    }
}
""", '5\n-7\n4\n0\n')

    def test_bind_and_fn_values(self):
        self.assertOutput("""
fn add { a: i32, b: i32 } -> i32 { return a + b }
fn apply { f: &fn{ b: i32 } -> i32, x: i32 } -> i32 { return f{ b = x } }
fn twice { f: fn{ a: i32, b: i32 } -> i32 } -> i32 { return f{ a = 2, b = 3 } * 2 }
fn count { mut n: i32, by: i32 } { n = n + by }
fn main { mut io: Io } {
    let add5 = add{ a = 5, _ }
    io::println_i64{ &io, n = apply{ f = add5, x = 10 } }
    io::println_i64{ &io, n = twice{ f = add } }
    let mut c = 0
    let inc = count{ n = &c, _ }
    inc{ by = 3 }
    inc{ by = 4 }
    io::println_i64{ &io, n = c }
}
""", '15\n10\n7\n')

    def test_bound_outlives(self):
        self.assertCompileError("""
fn count { mut n: i32, by: i32 } { n = n + by }
fn main { mut io: Io } {
    let mut c = 0
    let mut f = count{ n = &c, _ }
    if (true) {
        let mut d = 0
        f = count{ n = &d, _ }
    }
}
""", 'does not live as long')

    def test_escape_assign_outer(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let mut x: i32 = 1
    let mut p = &x
    if (true) {
        let mut y: i32 = 2
        p = &y
    }
}
""", 'outlives local `y`')

    def test_escape_mut_field(self):
        self.assertCompileError("""
struct Box { p: ?*i32 }
fn put { mut b: Box } { let mut x = 1; b.p = &x }
fn main { mut io: Io } { }
""", 'belongs to the caller')

    def test_consts_and_namespaces(self):
        self.assertOutput("""
namespace geo {
    const N: usize = 4
    struct V { x: i32, y: i32 }
    const ORIGIN: V = V{ x = 1, y = 2 }
    fn dot { a: V, b: V } -> i32 { return a.x * b.x + a.y * b.y }
}
fn main { mut io: Io } {
    let mut arr: [geo::N * 2]u8
    io::println_u64{ &io, n = arr.len }
    io::println_i64{ &io, n = geo::dot{ a = geo::ORIGIN, b = geo::V{ x = 3, y = 4 } } }
    io::println_u64{ &io, n = @size_of(geo::V) }
}
""", '8\n11\n8\n')

    def test_const_address(self):
        self.assertCompileError("""
const C: i32 = 1
fn main { mut io: Io } { let p = &C }
""", 'is a const, not a place')

    def test_else_unreachable(self):
        self.assertCompileError("""
union U { a, b }
fn main { mut io: Io } { let u = U::a; match (u) { a => { } b => { } else => { } } }
""", 'unreachable')

    def test_recursion_stack_overflow(self):
        with self.assertRaises(Trap):
            run_source("""
fn r { n: u64 } -> u64 { let mut big: [1024]u64; return r{ n = n + 1 } }
fn main { mut io: Io } { let x = r{ n = 0 } }
""", out=io.StringIO(), stack_size=1 << 20)


class LoopControl(Base):
    def test_break_and_continue(self):
        self.assertOutput("""
fn first_even { a: [5]i32 } -> ?usize {
    let mut i: usize = 0
    let mut found: ?usize = null
    while (i < a.len) {
        if (a[i] % 2 == 0) { found = i; break }
        i = i + 1
    }
    return found
}
fn main { mut io: Io } {
    let r = first_even{ a = [1, 3, 8, 5, 6] }
    if (r != null) { io::println_u64{ &io, n = r } }
    let mut sum = 0
    let mut i = 0
    while (i < 10) {
        i = i + 1
        if (i % 2 == 1) { continue }
        sum = sum + i
    }
    io::println_i64{ &io, n = sum }
}
""", '2\n30\n')

    def test_break_exits_innermost_loop(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let mut i = 0
    let mut hits = 0
    while (i < 3) {
        let mut j = 0
        while (true) {
            j = j + 1
            if (j == 4) { break }
            hits = hits + 1
        }
        i = i + 1
    }
    io::println_i64{ &io, n = hits }
}
""", '9\n')

    def test_break_inside_match(self):
        self.assertOutput("""
union Cmd { add{ n: i32 }, stop }
fn main { mut io: Io } {
    let cmds = [Cmd::add{ n = 2 }, Cmd::add{ n = 5 }, Cmd::stop, Cmd::add{ n = 100 }]
    let mut total = 0
    let mut i: usize = 0
    while (i < cmds.len) {
        match (cmds[i]) {
            add{ n } => { total = total + n }
            stop     => { break }
        }
        i = i + 1
    }
    io::println_i64{ &io, n = total }
}
""", '7\n')

    def test_break_outside_loop(self):
        self.assertCompileError('fn main { mut io: Io } { break }', '`break` outside a loop')
        self.assertCompileError('fn main { mut io: Io } { continue }', '`continue` outside a loop')

    def test_infinite_loop_ends_path(self):
        self.assertOutput("""
fn spin {} -> i32 {
    let mut n = 0
    while (true) {
        n = n + 1
        if (n < 10) { continue }
        return n
    }
}
fn main { mut io: Io } { io::println_i64{ &io, n = spin{} } }
""", '10\n')

    def test_loop_with_break_needs_return(self):
        self.assertCompileError("""
fn f {} -> i32 { while (true) { break } }
fn main { mut io: Io } { }
""", 'must end every path')

    def test_assign_once_then_break(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let x: i32
    while (true) { x = 7; break }
    io::println_i64{ &io, n = x }
}
""", '7\n')

    def test_assign_in_repeating_loop(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let x: i32
    let mut i = 0
    while (i < 3) { x = i; i = i + 1 }
}
""", 'assigned in a loop that can repeat')

    def test_assign_before_continue(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let x: i32
    while (true) { x = 1; continue }
}
""", 'assigned in a loop that can repeat')


class Widening(Base):
    def test_widening_sites(self):
        self.assertOutput("""
struct S { big: i64 }
fn take { n: u64 } -> u64 { return n }
fn ret { n: i8 } -> i32 { return n }
fn main { mut io: Io } {
    let a: u8 = 200
    let b: i16 = -300
    let c: u32 = 4000000000
    let len: usize = 3
    io::println_u64{ &io, n = take{ n = a } }
    io::println_u64{ &io, n = len }
    io::println_i64{ &io, n = b }
    io::println_i64{ &io, n = c }
    io::println_i64{ &io, n = ret{ n = -5 } }
    let s = S{ big = a }
    io::println_i64{ &io, n = s.big }
    let o: ?i64 = b
    if (o != null) { io::println_i64{ &io, n = o } }
    let mut w: i64 = 0
    w = c
    io::println_i64{ &io, n = w }
    let f: f32 = 0.5
    let d: f64 = f
    io::println_f64{ &io, n = d }
}
""", '200\n3\n-300\n4000000000\n-5\n200\n-300\n4000000000\n0.5\n')

    def test_mixed_operands(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let a: u8 = 250
    let b: u32 = 10
    let s = a + b                   // u32: no u8 overflow
    io::println_u64{ &io, n = s }
    let i: i32 = -1
    let big: i64 = 5000000000
    io::println_i64{ &io, n = big + i }
    io::println_bool{ &io, n = a < b }
    let len: usize = 4
    let k: u8 = 3
    io::println_bool{ &io, n = k < len }
    let f: f32 = 1.5
    io::println_f64{ &io, n = f * 2.0 }
}
""", '260\n4999999999\nfalse\ntrue\n3.0\n')

    def test_wider_result_traps_at_wider_range(self):
        self.assertTrap("""
fn main { mut io: Io } { let a: u32 = 4000000000; let b: u8 = 1; let c = a * b * @as(u32, 2) }
""", 'integer overflow')

    def test_no_narrowing(self):
        self.assertCompileError('fn main { mut io: Io } { let a: i64 = 1; let b: i32 = a }',
                                'expected i32, got i64')

    def test_no_sign_change(self):
        self.assertCompileError('fn main { mut io: Io } { let a: i32 = 1; let b: u64 = a }',
                                'expected u64, got i32')
        self.assertCompileError('fn main { mut io: Io } { let a: u64 = 1; let b: i64 = a }',
                                'expected i64, got u64')

    def test_signed_unsigned_operands(self):
        self.assertCompileError('fn main { mut io: Io } { let a: i32 = 1; let b: u32 = 2; let c = a < b }',
                                'cannot compare i32 with u32')

    def test_no_int_to_float(self):
        self.assertCompileError('fn main { mut io: Io } { let a: i32 = 1; let b: f64 = a }',
                                'expected f64, got i32')

    def test_usize_only_to_u64(self):
        self.assertCompileError('fn main { mut io: Io } { let a: usize = 1; let b: i64 = a }',
                                'expected i64, got usize')
        self.assertCompileError('fn main { mut io: Io } { let a: u64 = 1; let b: usize = a }',
                                'expected usize, got u64')

    def test_no_widening_through_pointers_or_optionals(self):
        self.assertCompileError('fn main { mut io: Io } { let mut a: i32 = 1; let p: *i64 = &a }',
                                'expected *i64, got *i32')
        self.assertCompileError('fn main { mut io: Io } { let a: ?i32 = 1; let b: ?i64 = a }',
                                'expected ?i64, got ?i32')

    def test_mut_field_needs_exact_type(self):
        self.assertCompileError("""
fn bump { mut n: i64 } { n = n + 1 }
fn main { mut io: Io } { let mut a: i32 = 1; bump{ n = &a } }
""", 'expected *i64, got *i32')


def run_io(src, stdin=b''):
    out, err = io.StringIO(), io.StringIO()
    run_source(src, out=out, err=err, inp=io.BytesIO(stdin))
    return out.getvalue(), err.getvalue()


class StdLib(Base):
    def test_hello(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let hi = "hello, \\"world\\"\\t!"
    io::println{ &io, s = ascii::of{ chars = &hi } }
    io::put_char{ &io, c = 'x' }
    io::newline{ &io }
}
""", 'hello, "world"\t!\nx\n')

    def test_stderr(self):
        out, err = run_io("""
fn main { mut io: Io } {
    let a = "out"
    let b = "err"
    io::println{ &io, s = ascii::of{ chars = &a } }
    io::eprintln{ &io, s = ascii::of{ chars = &b } }
}
""")
        self.assertEqual((out, err), ('out\n', 'err\n'))

    def test_number_formatting(self):
        self.assertOutput("""
fn main { mut io: Io } {
    io::println_i64{ &io, n = -9223372036854775808 }
    io::println_i64{ &io, n = 0 }
    io::println_u64{ &io, n = 18446744073709551615 }
    io::println_i64{ &io, n = -128 }
    io::println_u64{ &io, n = 7 }
    io::println_f64{ &io, n = 3.0 }
    io::println_f64{ &io, n = 1e100 }
    io::println_f64{ &io, n = -0.1 }
    io::println_f32{ &io, n = 1.1 }
    io::println_bool{ &io, n = false }
    io::print_i64{ &io, n = 1 }
    io::print_i64{ &io, n = 2 }
    io::newline{ &io }
}
""", '-9223372036854775808\n0\n18446744073709551615\n-128\n7\n3.0\n1e+100\n-0.1\n1.1\nfalse\n12\n')

    def test_parse(self):
        self.assertOutput("""
fn show { mut io: Io, r: ?i64 } {
    match (r) {
        null => { io::println_i64{ &io, n = 0 } }
        some{ value } => { io::println_i64{ &io, n = value } }
    }
}
fn main { mut io: Io } {
    let a = "-9223372036854775808"
    let b = "9223372036854775808"
    let c = "12x"
    let d = "-"
    let e = "0042"
    show{ &io, r = ascii::parse_i64{ s = ascii::of{ chars = &a } } }
    show{ &io, r = ascii::parse_i64{ s = ascii::of{ chars = &b } } }
    show{ &io, r = ascii::parse_i64{ s = ascii::of{ chars = &c } } }
    show{ &io, r = ascii::parse_i64{ s = ascii::of{ chars = &d } } }
    show{ &io, r = ascii::parse_i64{ s = ascii::of{ chars = &e } } }
    let u = "18446744073709551616"
    io::println_bool{ &io, n = ascii::parse_u64{ s = ascii::of{ chars = &u } } == null }
}
""", '-9223372036854775808\n0\n0\n0\n42\ntrue\n')

    def test_string_ops(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let raw = "  Hello, World \\n"
    let s = ascii::trim{ s = ascii::of{ chars = &raw } }
    io::println{ &io, s }
    io::println_u64{ &io, n = ascii::len{ s } }
    let hel = "Hello"
    let rld = "rld"
    io::println_bool{ &io, n = ascii::starts_with{ s, prefix = ascii::of{ chars = &hel } } }
    io::println_bool{ &io, n = ascii::ends_with{ s, suffix = ascii::of{ chars = &rld } } }
    io::println_bool{ &io, n = ascii::eq{ a = s, b = ascii::of{ chars = &hel } } }
    let comma = ascii::find{ s, c = ',' }
    if (comma != null) {
        io::println{ &io, s = ascii::sub{ s, lo = 0, hi = comma } }
    }
    io::put_char{ &io, c = ascii::to_upper{ c = 'q' } }
    io::put_char{ &io, c = ascii::to_lower{ c = 'Q' } }
    io::newline{ &io }
}
""", 'Hello, World\n12\ntrue\ntrue\nfalse\nHello\nQq\n')

    def test_builder(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let mut mem: [1024]u8
    let mut heap = arena::new{ buf = slice::of(u8){ a = &mem } }
    let mut b = ascii::builder{ realloc = arena::alloc }
    let name = "count"
    ascii::push{ &b, &heap, s = ascii::of{ chars = &name } }
    ascii::push_char{ &b, &heap, c = '=' }
    ascii::push_i64{ &b, &heap, n = -1234567 }
    ascii::push_char{ &b, &heap, c = ' ' }
    ascii::push_u64{ &b, &heap, n = 99 }
    io::println{ &io, s = ascii::view{ b } }
    ascii::free{ &b, &heap }
    io::println_u64{ &io, n = ascii::len{ s = ascii::view{ b } } }
}
""", 'count=-1234567 99\n0\n')

    def test_read_line(self):
        out, _ = run_io("""
fn main { mut io: Io } {
    let mut buf: [8]u8
    let mut total: i64 = 0
    let mut more = true
    while (more) {
        let line = io::read_line{ &io, into = slice::of(u8){ a = &buf } }
        if (line == null) {
            more = false
        } else {
            let n = ascii::parse_i64{ s = ascii::trim{ s = line } }
            if (n != null) { total = total + n }
            io::println{ &io, s = line }
        }
    }
    io::println_i64{ &io, n = total }
}
""", b'12\r\n30\nabcdefghij\n  -2\nlast')
        self.assertEqual(out, '12\n30\nabcdefgh\nij\n  -2\nlast\n40\n')

    def test_slice_helpers(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let mut a: [5]i32
    let s = slice::of(i32){ a = &a }
    slice::fill{ s, v = 3 }
    slice::set{ s, i = 4, v = 9 }
    io::println_i64{ &io, n = a[0] + a[4] }
    io::println_u64{ &io, n = s.len }
    io::println_bool{ &io, n = slice::is_empty{ s = slice::sub{ s, lo = 2, hi = 2 } } }
}
""", '12\n5\ntrue\n')

    def test_non_ascii_traps(self):
        self.assertTrap("""
fn main { mut io: Io } {
    let b = "caf\\xe9"
    io::println{ &io, s = ascii::of{ chars = &b } }
}
""", '@trap()')

    def test_non_ascii_literal_rejected(self):
        self.assertCompileError('fn main { mut io: Io } { let b = "café" }', 'non-ASCII')

    def test_slice_bounds_trap(self):
        self.assertTrap("""
fn main { mut io: Io } {
    let mut a: [2]u8
    let s = slice::of(u8){ a = &a }
    let x = slice::get{ s, i = 2 }
}
""", '@trap()')

    def test_io_needs_capability(self):
        self.assertCompileError("""
fn helper { n: i32 } { io::println_i64{ n } }
fn main { mut io: Io } { }
""", 'missing `io`')

    def test_user_namespace_shadows_std(self):
        self.assertOutput("""
namespace slice { fn answer {} -> i32 { return 42 } }
fn main { mut io: Io } { io::println_i64{ &io, n = slice::answer{} } }
""", '42\n')

    def test_string_literal_escape_check(self):
        self.assertCompileError("""
fn greet {} -> ascii::String {
    let hi = "hi"
    return ascii::of{ chars = &hi }
}
fn main { mut io: Io } { }
""", 'returned value holds the address of local `hi`')

    def test_trap_in_std_reports_std_file(self):
        with self.assertRaises(Trap) as cm:
            run_source("""
fn main { mut io: Io } {
    let mut a: [2]u8
    let x = slice::get{ s = slice::of(u8){ a = &a }, i = 5 }
}
""", 'user.ctx', out=io.StringIO())
        self.assertEqual(cm.exception.pos[2], 'std/slice.ctx')

    def test_error_reports_user_file(self):
        with self.assertRaises(CompileError) as cm:
            run_source('fn main { mut io: Io } { io::println_i64{ &io, n = "x" } }', 'user.ctx')
        self.assertEqual(cm.exception.pos[2], 'user.ctx')
        self.assertIn('expected i64, got [1]u8', cm.exception.msg)


if __name__ == '__main__':
    unittest.main()
