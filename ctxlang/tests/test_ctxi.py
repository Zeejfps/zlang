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
        self.assertOutput(LIB + MAIN_SETUP % '    io::print_i32{ &io, n = total }', '0\n')

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
        self.lib_error('    io::print_i32{ &io, n = list::get{ list = nums, i = 0 } }',
                       'expected i32, got ?i32')

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
        push{ value } => { io::print_i32{ &io, n = value } }
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
    if (maybe != null) { io::print_i32{ &io, n = maybe } }""", 'expected i32, got ?i32')

    def test_not_caught_wrong_instance(self):
        self.assertOutput(LIB + MAIN_SETUP % """
    let mut mem2: [256]u8
    let mut other = arena::Arena{ buf = slice::from{ ptr = &mem2[0], len = mem2.len }, used = 0 }
    list::push{ list = &nums, heap = &other, item = 1 }
    io::print_usize{ &io, n = nums.len }""", '1\n')


class Basics(Base):
    def test_arith_and_loops(self):
        self.assertOutput("""
fn fib { n: u64 } -> u64 {
    if (n < 2) { return n }
    return fib{ n = n - 1 } + fib{ n = n - 2 }
}
fn main { mut io: Io } {
    io::print_u64{ &io, n = fib{ n = 20 } }
    let mut i = 0
    let mut s: i64
    while (i < 10) { s = s + @as(i64, i); i = i + 1 }
    io::print_i64{ &io, n = s }
    io::print_i32{ &io, n = -7 / 2 }
    io::print_i32{ &io, n = -7 % 2 }
    io::print_f64{ &io, n = 1.5 * 2.0 }
    io::print_bool{ &io, n = 3 > 2 and not (1 == 2) }
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
    io::print_i32{ &io, n = a[i] }
}
""", 'out of bounds')

    def test_explicit_trap(self):
        self.assertTrap('fn main { mut io: Io } { @trap() }', '@trap()')

    def test_wrap_and_trunc(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let x: u8 = 250
    io::print_u8{ &io, n = @wrap_add(x, 10) }
    io::print_i8{ &io, n = @trunc(i8, 200) }
    io::print_i32{ &io, n = @as(i32, 3.9) }
    io::print_i32{ &io, n = @as(i32, -3.9) }
    io::print_f64{ &io, n = @as(f64, 7) }
}
""", '4\n-56\n3\n-3\n7.0\n')

    def test_as_traps(self):
        self.assertTrap("""
fn main { mut io: Io } { let x: i32 = 300; io::print_u8{ &io, n = @as(u8, x) } }
""", 'not representable')

    def test_literal_range(self):
        self.assertCompileError('fn main { mut io: Io } { let x: u8 = 300 }', 'does not fit in u8')

    def test_mixed_types(self):
        self.assertCompileError("""
fn main { mut io: Io } { let a: i32 = 1; let b: i64 = 2; let c = a + b }
""", 'different types')

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
    io::print_i32{ &io, n = sum{ p = a } }
    io::print_i32{ &io, n = sum{ p = b } }
    let mut arr = [P{ x = 1, y = 1 }; 3]
    arr[2].y = 9
    let pa = &arr
    io::print_i32{ &io, n = pa[2].y + @as(i32, pa.len) }
    let p0 = &arr[0]
    io::print_i32{ &io, n = (p0 + 2).*.y }
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
        ok{ value } => { io::print_i32{ &io, n = value } }
        err{ code } => { io::print_i32{ &io, n = -code } }
    }
}
fn first(T) { a: [3]T } -> ?T { return a[0] }
fn main { mut io: Io } {
    show{ &io, r = half{ n = 10 } }
    show{ &io, r = half{ n = 7 } }
    let f = first{ a = [4, 5, 6] }
    if (f == null) { } else { io::print_i32{ &io, n = f } }
    let none: ?i32 = null
    match (none) {
        null => { io::print_i32{ &io, n = 0 } }
        some{ value } => { io::print_i32{ &io, n = value } }
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
    io::print_i32{ &io, n = apply{ f = add5, x = 10 } }
    io::print_i32{ &io, n = twice{ f = add } }
    let mut c = 0
    let inc = count{ n = &c, _ }
    inc{ by = 3 }
    inc{ by = 4 }
    io::print_i32{ &io, n = c }
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
    io::print_usize{ &io, n = arr.len }
    io::print_i32{ &io, n = geo::dot{ a = geo::ORIGIN, b = geo::V{ x = 3, y = 4 } } }
    io::print_usize{ &io, n = @size_of(geo::V) }
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


if __name__ == '__main__':
    unittest.main()
