"""Tests for ctxlang, through the native ctxc (tools/toolchain.py).  Run:  python -m unittest discover tests"""

import io
import os
import shutil
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from toolchain import CompileError, Panic, read_program, run_source, run_sources  # noqa: E402

with open(os.path.join(ROOT, 'examples', 'list.ctx'), encoding='utf-8') as f:
    LIST_SRC = f.read()
LIB = LIST_SRC[:LIST_SRC.index('fn main {')]

MAIN_SETUP = """
fn main { mut io: Io } {
    let mut mem: [4096]u8
    let mut heap = arena::Arena{ buf = @slice(&mem[0], mem.len), used = 0 }
    let mut nums = list::new(i32){ realloc = arena::alloc, &heap }
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

    def assertPanic(self, src, fragment):
        with self.assertRaises(Panic) as cm:
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
    let xs = list::new(i32){ realloc = arena::alloc, heap = &m }""", 'expected')

    def test_list_outlives_heap(self):
        # A list holds a pointer to its allocator's state, so it can't outlive a local one.
        self.assertCompileError("""
fn make {} -> list::List(i32, arena::Arena) {
    let mut heap = arena::new{ buf = slice::empty(u8){} }
    return list::new(i32){ realloc = arena::alloc, &heap }
}
fn main {} { _ = make{} }
""", 'returned value holds the address of local `heap`')

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
        self.lib_error('    let l = list::new(i32){ realloc = log_to{ log = &io, _ }, &heap }', 'got &fn', extra)

    def test_not_exhaustive(self):
        self.lib_error("""
    let ev = Event::pop
    match ev { push{ value } => { } }""", "match isn't exhaustive: missing pop, clear")

    def test_optional_not_unwrapped(self):
        self.lib_error('    io::println_i64{ &io, n = list::get{ list = nums, i = 0 } }',
                       'expected i64, got ?i32')

    def test_two_mut_refs(self):
        extra = 'fn move_first(S) { mut from: list::List(i32, S), mut to: list::List(i32, S), mut heap: S } { }\n'
        self.lib_error('    move_first{ from = &nums, to = &nums, .. }', 'two mut references to `nums`', extra)

    def test_match_scrutinee_overlap(self):
        self.lib_error("""
    let mut ev = Event::push{ value = 1 }
    match &ev {
        push{ &value } => { ev = Event::pop; value = 2 }
        else           => { }
    }""", 'ev overlaps the match scrutinee; access it only through `value`')

    def test_match_scrutinee_binding_ok(self):
        self.assertOutput(LIB + MAIN_SETUP % """
    let mut ev = Event::push{ value = 1 }
    match &ev {
        push{ &value } => { value = 7 }
        else           => { }
    }
    match ev {
        push{ value } => { io::println_i64{ &io, n = value } }
        else          => { }
    }""", '7\n')

    def test_maybe_unassigned(self):
        self.lib_error("""
    let ev: Event
    if total > 100 { ev = Event::clear }
    apply{ &nums, ev, .. }""", '`ev` may be read before it is assigned')

    def test_held_overlap(self):
        extra = 'fn sum_into { mut total: i32, f: &fn{ item: i32 } } { }\n'
        self.lib_error("""
    let f = add_to{ &total, _ }
    sum_into{ &total, f }""", '`total` overlaps a place held by `f`', extra)

    def test_escape_return(self):
        extra = """fn make_arena {} -> arena::Arena {
    let mut mem: [64]u8
    return arena::Arena{ buf = @slice(&mem[0], mem.len), used = 0 }
}
"""
        self.lib_error('', 'returned value holds the address of local `mem`', extra)

    def test_mutable_not_narrowed(self):
        self.lib_error("""
    let mut maybe = list::get{ list = nums, i = 0 }
    if maybe != null { io::println_i64{ &io, n = maybe } }""", 'expected i64, got ?i32')

    def test_not_caught_wrong_instance(self):
        self.assertOutput(LIB + MAIN_SETUP % """
    let mut mem2: [256]u8
    let mut other = arena::Arena{ buf = @slice(&mem2[0], mem2.len), used = 0 }
    _ = list::push{ list = &nums, item = 1 }
    io::println_u64{ &io, n = nums.len }""", '1\n')


class Basics(Base):
    def test_arith_and_loops(self):
        self.assertOutput("""
fn fib { n: u64 } -> u64 {
    if n < 2 { return n }
    return fib{ n = n - 1 } + fib{ n = n - 2 }
}
fn main { mut io: Io } {
    io::println_u64{ &io, n = fib{ n = 20 } }
    let mut i = 0
    let mut s: i64
    while i < 10 { s = s + @as(i64, i); i = i + 1 }
    io::println_i64{ &io, n = s }
    io::println_i64{ &io, n = -7 / 2 }
    io::println_i64{ &io, n = -7 % 2 }
    io::println_f64{ &io, n = 1.5 * 2.0 }
    io::println_bool{ &io, n = 3 > 2 and not (1 == 2) }
}
""", '6765\n45\n-3\n-1\n3.0\n true\n'.replace(' ', ''))

    def test_overflow_panics(self):
        self.assertPanic("""
fn main { mut io: Io } {
    let mut x: u8 = 250
    while true { x = x + 1 }
}
""", 'integer overflow')

    def test_unsigned_underflow_panics(self):
        self.assertPanic("""
fn main { mut io: Io } {
    let a: usize = 1
    let b = a - 2
}
""", 'integer overflow')

    def test_div_zero_panics(self):
        self.assertPanic("""
fn d { a: i32, b: i32 } -> i32 { return a / b }
fn main { mut io: Io } { let x = d{ a = 1, b = 0 } }
""", 'division by zero')

    def test_bounds_panic(self):
        self.assertPanic("""
fn main { mut io: Io } {
    let a = [1, 2, 3]
    let mut i: usize = 3
    io::println_i64{ &io, n = a[i] }
}
""", 'out of bounds')

    def test_explicit_panic(self):
        self.assertPanic('fn main { mut io: Io } { @panic() }', '@panic()')

    def test_panic_with_reason(self):
        with self.assertRaises(Panic) as cm:
            run('fn main { mut io: Io } { @panic("cache is cold") }')
        self.assertEqual(cm.exception.msg, 'cache is cold')

    def test_panic_reason_escapes_non_ascii(self):
        self.assertPanic(r'fn main { mut io: Io } { @panic("caf\xe9") }', r'caf\xe9')

    def test_panic_reason_ends_a_path(self):
        self.assertOutput("""
fn pick { n: i32 } -> i32 {
    let r = if n == 1 { 10 } else { @panic("unexpected n") }
    if n > 0 { return r }
    @panic("n must be positive")
}
fn main { mut io: Io } { io::println_i64{ &io, n = pick{ n = 1 } } }
""", '10\n')

    def test_panic_reason_must_be_literal(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let why = "no"
    @panic(why)
}
""", '@panic takes a string literal')

    def test_bitwise(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let a: u32 = 0xF0
    io::println_u64{ &io, n = a & 0x3C }
    io::println_u64{ &io, n = a | 0x0F }
    io::println_u64{ &io, n = a ^ 0xFF }
    let b: i8 = -6
    io::println_i64{ &io, n = b & 0x0F }
    io::println_i64{ &io, n = b ^ -1 }
    let c: u8 = 3
    io::println_u64{ &io, n = a | c }
}
""", '48\n255\n15\n10\n5\n243\n')

    def test_shifts(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let a: u32 = 0xF0
    let n: usize = 24
    io::println_u64{ &io, n = a << n }
    io::println_u64{ &io, n = a << 28 }
    io::println_u64{ &io, n = a >> 4 }
    let one: i8 = 1
    io::println_i64{ &io, n = one << 7 }
    let b: i8 = -128
    io::println_i64{ &io, n = b >> 7 }
    let big: u64 = 256 << 20
    io::println_u64{ &io, n = big }
}
""", '4026531840\n0\n15\n-128\n-1\n268435456\n')

    def test_bitwise_precedence(self):
        self.assertOutput("""
fn main { mut io: Io } {
    io::println_i64{ &io, n = 1 | 2 ^ 3 & 4 << 1 }
    io::println_i64{ &io, n = 1 << 2 + 1 }
    io::println_bool{ &io, n = 6 & 1 == 0 }
    io::println_i64{ &io, n = (1 | 2) ^ 3 }
}
""", '3\n8\ntrue\n0\n')

    def test_shift_count_too_big_panics(self):
        self.assertPanic("""
fn main { mut io: Io } {
    let x: u32 = 1
    let n: u8 = 32
    io::println_u64{ &io, n = x << n }
}
""", 'shift count 32 out of range for a 32-bit integer')

    def test_shift_count_negative_panics(self):
        self.assertPanic("""
fn main { mut io: Io } {
    let x: i64 = 1
    let n = -1
    io::println_i64{ &io, n = x >> n }
}
""", 'shift count -1 out of range for a 64-bit integer')

    def test_bitwise_needs_integers(self):
        self.assertCompileError("""
fn main { mut io: Io } { let x = 1.5 & 2.0 }
""", '`&` needs integers, got {float}')
        self.assertCompileError("""
fn main { mut io: Io } { let x = true | false }
""", '`|` needs integers, got bool')
        self.assertCompileError("""
fn main { mut io: Io } { let x = 1.5 << 2 }
""", '`<<` needs an integer to shift, got {float}')
        self.assertCompileError("""
fn main { mut io: Io } { let x = 1 >> 2.0 }
""", 'a shift count must be an integer, got {float}')

    def test_bitwise_in_array_length(self):
        self.assertOutput("""
const K: usize = 1 << 3
fn main { mut io: Io } {
    let mut a: [K | 1]u8
    io::println_u64{ &io, n = a.len }
}
""", '9\n')

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

    def test_as_panics(self):
        self.assertPanic("""
fn main { mut io: Io } { let x: i32 = 300; io::println_u64{ &io, n = @as(u8, x) } }
""", 'not representable')

    def test_literal_range(self):
        self.assertCompileError('fn main { mut io: Io } { let x: u8 = 300 }', 'does not fit in u8')

    def test_literal_range_names_the_operand(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let b: u8 = 3
    let mut x = 0
    x = 1000
    io::println_u64{ &io, n = x + b }
}
""", 'literal 1000 does not fit in u8, which it gets from `b` at 6:35')

    def test_mixed_types(self):
        self.assertCompileError("""
fn main { mut io: Io } { let a: i32 = 1; let b: u32 = 2; let c = a + b }
""", 'incompatible types')

    def test_float_remainder(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let a = 7.5
    let b: f32 = -7.5
    io::println_f64{ &io, n = a % 2.0 }
    io::println_f32{ &io, n = b % 2.0 }
}
""", "1.5\n-1.5\n")

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
fn f { a: i32 } -> i32 { if a > 0 { return 1 } }
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
    if n % 2 != 0 { return Result::err{ code = n } }
    return Result::ok{ value = n / 2 }
}
fn show { mut io: Io, r: Result(i32) } {
    match r {
        ok{ value } => { io::println_i64{ &io, n = value } }
        err{ code } => { io::println_i64{ &io, n = -code } }
    }
}
fn first(T) { a: [3]T } -> ?T { return a[0] }
fn main { mut io: Io } {
    show{ &io, r = half{ n = 10 } }
    show{ &io, r = half{ n = 7 } }
    let f = first{ a = [4, 5, 6] }
    if f == null { } else { io::println_i64{ &io, n = f } }
    let none: ?i32 = null
    match none {
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
    if true {
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
    if true {
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
fn main { mut io: Io } { let u = U::a; match u { a => { } b => { } else => { } } }
""", 'unreachable')

    def test_recursion_stack_overflow(self):
        with self.assertRaises(Panic):
            run_source("""
fn r { n: u64 } -> u64 { let mut big: [1024]u64; return r{ n = n + 1 } }
fn main { mut io: Io } { let x = r{ n = 0 } }
""", out=io.StringIO(), stack_size=1 << 20)


class Lexer(Base):
    def assertLexError(self, src, msg, line, col):
        with self.assertRaises(CompileError) as cm:
            run(src)
        self.assertEqual((cm.exception.msg, cm.exception.pos[:2]), (msg, (line, col)), src)

    def test_literals(self):
        for src, msg, line, col in [
            ('fn main {\n    let s = "abc\n}', 'unterminated literal', 2, 13),
            ('fn main { let s = "abc\\', 'unterminated literal', 1, 19),
            ("fn main { let c = 'a }", 'a character literal holds exactly one character', 1, 19),
            ("fn main { let c = 'ab' }", 'a character literal holds exactly one character', 1, 19),
            ("fn main { let c = '' }", 'a character literal holds exactly one character', 1, 19),
            ("fn main { let c = ''' }", 'a character literal holds exactly one character', 1, 19),
            ('fn main { let s = "\\q" }', 'unknown escape \\q', 1, 19),
            ('fn main { let s = "\\x4" }', '\\x needs two hex digits', 1, 19),
            ('fn main { let s = "\\xZZ" }', '\\x needs two hex digits', 1, 19),
            ('fn main { let s = "café" }',
             "non-ASCII character 'é' (U+00E9) in literal; use a \\x escape", 1, 19),
        ]:
            self.assertLexError(src, msg, line, col)

    def test_numbers(self):
        for src in ['12ab', '0x', '0b', '0x_', '1.5e3x', '0x1g']:
            self.assertLexError(f'fn main {{ let n = {src} }}', 'invalid number literal', 1, 19)

    def test_characters(self):
        for src, msg, col in [
            ('fn main { let n = 1 $ 2 }', "unexpected character '$'", 21),
            ('fn main { let n = \x01 }', "unexpected character '\\x01'", 19),
            ('fn main { let n = \\ }', "unexpected character '\\\\'", 19),
            ('fn main { let café = 1 }', "unexpected character 'é' (U+00E9)", 18),
            ('fn main { let n = 1² }', "unexpected character '²' (U+00B2)", 20),   # not a digit
            ('﻿fn main {}', "unexpected character '﻿' (U+FEFF)", 1),
            ('fn main { @ size_of(i32) }', "expected a builtin name after '@'", 11),
        ]:
            self.assertLexError(src, msg, 1, col)

    def test_comments(self):
        self.assertLexError('fn main {}\n/* never\nclosed', 'unterminated block comment', 2, 1)
        # The end of the file is after a trailing comment, not at its start.
        self.assertLexError('fn main { // open', 'expected a name, found end of file', 1, 18)
        self.assertOutput('// café ☃\nfn main { mut io: Io } { /* é\n */ io::println_i64{ &io, n = 1 } }', '1\n')

    def test_values(self):
        self.assertOutput(r"""
fn main { mut io: Io } {
    io::println_u64{ &io, n = 0x_ff + 0b1_0 + 1_000 }
    io::println_u64{ &io, n = '\'' + '\x41' }
    io::println_f64{ &io, n = 1_0.2_5e1 }
}
""", '1257\n104\n102.5\n')


class Parser(Base):
    """Every syntax error, at its exact position: tools/parsetest.py compares ctxc's first
    diagnostic with each of them through the corpus."""

    def assertParseError(self, src, msg, line, col):
        with self.assertRaises(CompileError) as cm:
            run(src)
        self.assertEqual((cm.exception.msg, cm.exception.pos[:2]), (msg, (line, col)), src)

    def test_declarations(self):
        for src, msg, line, col in [
            ('fn main {} {}\n}', "expected a declaration, found '}'", 2, 1),
            ('fn main {} {}\nlet x = 1', "expected a declaration, found 'let'", 2, 1),
            ('fn {} {}', "expected a name, found '{'", 1, 4),
            ('enum E(T): u8 { a }\nfn main {} {}', 'an enum cannot have generic parameters', 1, 7),
            ('enum E { a }\nfn main {} {}', "expected ':', found '{'", 1, 8),
            ('namespace n {\n    fn f {} {}\n', "expected '}' to close namespace", 3, 1),
            ('struct S { a i32 }\nfn main {} {}', "expected ':', found 'i32'", 1, 14),
            ('struct S { a: 5 }\nfn main {} {}', "expected a type, found '5'", 1, 15),
            ('type T =\nfn main {} {}', "expected '{', found 'main'", 2, 4),
            ('const N: i32 5\nfn main {} {}', "expected '=', found '5'", 1, 14),
            ('fn f(T {} {}\nfn main {} {}', "expected ')', found '{'", 1, 8),
            ('union U { a{ x: i32 } b }\nfn main {} {}', "expected '}', found 'b'", 1, 23),
            ('fn main {} -> {}', "expected a type, found '{'", 1, 15),
            ('fn main { mut io Io } {}', "expected ':', found 'Io'", 1, 18),
            # The first braces are the context: a body there gets its own message, a context
            # with a typo doesn't.
            ('fn main { let x = 1 }', "a function's context comes before its body: write `fn main {} { ... }`", 1, 9),
            ('fn main {\n    run{ n = 1 }\n}\nfn run { n: i32 } {}',
             "a function's context comes before its body: write `fn main {} { ... }`", 1, 9),
            ('fn f { a i32 } {}\nfn main {} {}', "expected ':', found 'i32'", 1, 10),
            ('fn main {} {}\nfn f { a: i32 }', "expected '{', found end of file", 2, 16),
        ]:
            self.assertParseError(src, msg, line, col)

    def test_statements(self):
        for body, msg, line, col in [
            ('let x = 1 let y = 2', "expected a newline or ';' after statement, found 'let'", 2, 15),
            ('let _ = 1', '`_` is not a name: `_ = e` discards a value without declaring anything', 2, 5),
            ('let x', '`let x` needs a type or an initializer', 2, 5),
            ('defer let x = 1', '`defer` takes a call, an assignment, `_ = e` or a block', 2, 5),
            ('outer: if true {}', "only a `while` can be labeled, found 'if'", 2, 12),
            ('let some{ value } = x', 'a `let` with a pattern needs an `else`', 3, 1),
            ('let null = x', 'a `let` with a pattern needs an `else`', 3, 1),
            ('let ok{ value } = r else err{ e } {', "expected '}' to close block", 3, 2),
            ('match x { a => {} b {} }', "expected '=>', found '}'", 2, 28),
            ('match x { a{ v w } => {} }', "expected '}', found 'w'", 2, 20),
            ('if x { } else y', "expected '{', found 'y'", 2, 19),
            ('while x', "expected '{', found '}'", 3, 1),
            ('break 5', "expected a newline or ';' after statement, found '5'", 2, 11),
            ('return 1 2', "expected a newline or ';' after statement, found '2'", 2, 14),
        ]:
            self.assertParseError('fn main {} {\n    %s\n}' % body, msg, line, col)
        self.assertParseError('fn main {} {\n    let x = 1\n', "expected '}' to close block", 3, 1)

    def test_expressions(self):
        for body, msg, line, col in [
            ('let v = if true { 1 }', 'an `if` expression needs an `else`', 2, 13),
            ('let b = 1 < 2 < 3', 'comparisons do not chain', 2, 19),
            ('f{ .., a }', "'..' must be the last item", 2, 12),
            ('f{ _, a }', "'_' must be the last item", 2, 11),
            ('let x = )', "expected an expression, found ')'", 2, 13),
            ('let x = a[1', "expected ']', found '}'", 3, 1),
            ('let x = a.', "expected a name, found '}'", 3, 1),
            ('let x = (1', "expected ')', found '}'", 3, 1),
            ('let x = [1, 2', "expected ']', found '}'", 3, 1),
            ('let x = [1; 2', "expected ']', found '}'", 3, 1),
            ('let x = a.b(i32)', "expected a newline or ';' after statement, found '('", 2, 16),
            ('let x = @nope(1)', 'unknown builtin `@nope`', 2, 13),
            ('@panic', 'expected \'(\' after @panic: @panic() or @panic("reason")', 3, 1),
            ('let x = @as(i32)', 'wrong number of arguments: @as(T, x)', 2, 20),
            ('let x = @size_of(i32, 1)', 'wrong number of arguments: @size_of(T)', 2, 27),
            ('let x = @fmt(b)', 'wrong number of arguments: @fmt(b, "format", args...)', 2, 19),
        ]:
            self.assertParseError('fn main {} {\n    %s\n}' % body, msg, line, col)

    def test_types(self):
        for body, msg, line, col in [
            ('let x: [3 = 1', "expected ']', found '='", 2, 15),
            ('let x: *mut = 1', "expected a type, found '='", 2, 17),
            ('let f: fn{ x } = g', "expected ':', found '}'", 2, 18),
            ('let f: list::List(i32 = g', "expected ')', found '='", 2, 27),
        ]:
            self.assertParseError('fn main {} {\n    %s\n}' % body, msg, line, col)

    def test_found(self):
        # A token is described as it is written.
        for body, found, col in [
            ('let x = "a" "b"', '\'"b"\'', 17),
            ('let x = 0x10 0x20', "'0x20'", 18),
            ("let x = 'a' 2.50", "'2.50'", 17),
            ('let x = 1 @size_of(i32)', "'@size_of'", 15),
        ]:
            self.assertParseError('fn main {} {\n    %s\n}' % body,
                                  "expected a newline or ';' after statement, found " + found, 2, col)


ENUM = """
enum Kind: u8 {
    ident,
    number,
    lbrace = 40,
    rbrace,
}

enum Sign: i8 { minus = -1, zero, plus }
"""


class Declarations(Base):
    """Every error in declarations, at its exact position: tools/checktest.py compares ctxc's
    first diagnostic with each of them through the corpus."""

    def assertDeclError(self, src, msg, line, col):
        with self.assertRaises(CompileError) as cm:
            run(src)
        self.assertEqual((cm.exception.msg, cm.exception.pos[:2]), (msg, (line, col)), src)

    def test_names(self):
        for src, msg, line, col in [
            ('struct S {}\nstruct S {}', '`S` is already declared in this scope', 2, 1),
            ('fn f {} {}\nconst f: i32 = 1', '`f` is already declared in this scope', 2, 1),
            ('namespace n {}\nstruct n {}', '`n` is already declared in this scope', 2, 1),
            ('namespace n { struct A {} }\nnamespace n { struct B {} }', '`n` is already declared in this scope', 2, 1),
            ('struct S(T, T) { a: T }', 'duplicate generic parameter in `S`', 1, 1),
            ('fn f(T, T) {} {}', 'duplicate generic parameter in `f`', 1, 1),
            ('struct S { a: Nope }', 'unknown type or namespace `Nope`', 1, 15),
            ('struct S { a: i32::x }', '`i32` is not a namespace', 1, 15),
            ('namespace n {}\nstruct S { a: n::Nope }', 'no type or namespace `Nope` in `n`', 2, 18),
            ('namespace n {}\nstruct S { a: n }', 'namespace `n` used as a type', 2, 15),
            ('fn f {} {}\nstruct S { a: f }', 'unknown type or namespace `f`', 2, 15),
        ]:
            self.assertDeclError(src + '\nfn main {} {}', msg, line, col)

    def test_types(self):
        for src, msg, line, col in [
            ('struct S { a: [0 - 1]u8 }', 'array length must not be negative', 1, 15),
            ('type F = fn{ a: i32, a: i32 }', 'duplicate context field `a`', 1, 22),
            ('fn f { a: i32, a: u8 } {}', 'duplicate context field `a`', 1, 16),
            ('struct S { f: &fn{} }', '`&fn` can only be the type of a local or a read-only context field', 1, 15),
            ('fn f { mut g: &fn{} } {}', '`&fn` can only be the type of a local or a read-only context field', 1, 15),
            ('fn f {} -> &fn{} {}', '`&fn` can only be the type of a local or a read-only context field', 1, 12),
            ('type F = &fn{}\nstruct S { f: F }', '`&fn` can only be the type of a local or a read-only context field', 1, 10),
            ('struct S(T) { a: T(i32) }', 'generic parameter `T` takes no type arguments', 1, 18),
            ('struct S { a: i32(u8) }', '`i32` takes no type arguments', 1, 15),
            ('struct S { a: Io(u8) }', '`Io` takes no type arguments', 1, 15),
            ('struct P(T) { a: T }\nstruct S { a: P }', '`P` expects 1 type argument(s), got 0', 2, 15),
            ('struct P(T) { a: T }\nstruct S { a: P(i32, u8) }', '`P` expects 1 type argument(s), got 2', 2, 15),
            ('type A = B\ntype B = A', 'type alias `A` refers to itself', 2, 10),
            ('type A = A', 'type alias `A` refers to itself', 1, 10),
            ('type A(T) = T(i32)\nstruct S { a: A(u8) }', 'generic parameter `T` takes no type arguments', 1, 13),
            ('struct S { a: i32, a: u8 }', 'duplicate field `a`', 1, 20),
            ('union U { a, a }', 'duplicate variant `a`', 1, 14),
            ('union U { a{ x: i32, x: u8 } }', 'duplicate field `x`', 1, 22),
            ('const C: Nope = 1', 'unknown type or namespace `Nope`', 1, 10),
        ]:
            self.assertDeclError(src + '\nfn main {} {}', msg, line, col)

    def test_constants(self):
        for src, msg, line, col in [
            ('struct S { a: [1 / 0]u8 }', 'division by zero in constant', 1, 18),
            ('struct S { a: [1 % 0]u8 }', 'division by zero in constant', 1, 18),
            ('struct S { a: [1 << 64]u8 }', 'shift count out of range in constant', 1, 18),
            ('const N: usize = N\nstruct S { a: [N]u8 }', 'const `N` refers to itself', 1, 18),
            ('const N: usize = M\nconst M: usize = N\nstruct S { a: [N]u8 }', 'const `N` refers to itself', 2, 18),
            ('struct S { a: [x]u8 }', 'array length must be a compile-time integer constant', 1, 16),
            ('struct S { a: [1.5]u8 }', 'array length must be a compile-time integer constant', 1, 16),
            ('namespace n { const N: usize = 2 }\nstruct S { a: [n::N * 3 - 1]u8 }\nconst B: [5]u8 = [0; 5]\nfn f { s: S } { let b: [5]u8 = s.a }', None, 0, 0),
            ('struct S { a: [nope::N]u8 }', 'unknown type or namespace `nope`', 1, 16),
            ('enum E: u8 { a = n::N }\nnamespace n { const N: u8 = 300 }', 'value 300 of `a` does not fit in u8', 1, 14),
        ]:
            if msg is None:
                run(src + '\nfn main {} {}')
            else:
                self.assertDeclError(src + '\nfn main {} {}', msg, line, col)

    def test_main(self):
        for src, msg, line, col in [
            ('', 'no `fn main` entry point', 1, 1),
            ('const main: i32 = 1', 'no `fn main` entry point', 1, 1),
            ('fn main(T) {} {}', '`main` cannot be generic', 1, 1),
            ('fn f {} {}\nfn main {} -> i64 { return 0 }', '`main` can only return i32 (the exit code), not i64', 2, 1),
            ('fn main { args: []u8 } {}', '`main` context field `args` must have type Args, got []u8', 1, 1),
            ('fn main { n: i32 } {}',
             '`main` context field `n` must have a capability type or be `args: Args`, got i32', 1, 1),
            ('fn main { mut args: Args } {}',
             '`main` context field `args` must have a capability type or be `args: Args`, got [][]u8', 1, 1),
        ]:
            self.assertDeclError(src, msg, line, col)
        run('fn main { args: [][]u8, mut io: Io, fs: Fs, mut mem: Mem } -> i32 { return 0 }')


class ConstInitializers(Base):
    """Const initializers, the first bodies the ctxc checker checks: every error at its exact
    position, for tools/checktest.py through the corpus."""

    def assertConstError(self, src, msg, line, col):
        with self.assertRaises(CompileError) as cm:
            run(src)
        self.assertEqual((cm.exception.msg, cm.exception.pos[:2]), (msg, (line, col)), src)

    def test_errors(self):
        for src, msg, line, col in [
            ('const A: u8 = 300', 'literal 300 does not fit in u8', 1, 15),
            ('const A: u8 = 1\nconst B: u8 = A + 300', 'literal 300 does not fit in u8, which it gets from `A` at 2:15', 2, 19),
            ('const A: i8 = -129', 'literal -129 does not fit in i8', 1, 15),
            ('const A: i32 = true', 'expected i32, got bool', 1, 16),
            ('const A: [2]u8 = [1, 2, 3]', 'expected [2]u8, got [3]u8', 1, 18),
            ('const A: [2]u8 = [1, true]', 'expected u8, got bool', 1, 22),
            ('struct P(T) { a: T }\nconst A: P(u8) = P(i64){ a = 1 }', 'expected P(u8), got P(i64)', 2, 24),
            ('struct P(T) { a: T }\nconst A: P(u8) = P{ a = 300 }', 'literal 300 does not fit in u8', 2, 25),
            ('struct S { a: i32, b: i32 }\nconst A: S = S{ a = 1 }', 'struct `S` is missing `b`', 2, 15),
            ('struct S { a: i32 }\nconst A: S = S{ a = 1, c = 2 }', 'struct `S` has no field `c`', 2, 24),
            ('struct S { a: i32 }\nconst A: S = S{ a = 1, a = 2 }', '`a` is supplied more than once', 2, 24),
            ('union U { a, b{ x: i32 } }\nconst A: U = U::b', 'variant `b` has a payload; construct it with `U::b{ ... }`', 2, 14),
            ('union U { a, b{ x: i32 } }\nconst A: U = U::a{}', 'variant `a` has no payload; write it without braces', 2, 18),
            ('union U { a, b{ x: i32 } }\nconst A: U = U::c', 'U has no variant `c`', 2, 17),
            ('enum E: u8 { a }\nconst A: E = E::a{}', '`E::a` is an enum value; write it without braces', 2, 18),
            ('struct S { a: i32 }\nconst A: S = S', '`S` is a type, not a value', 2, 14),
            ('const A: i32 = nope', 'unknown name `nope`', 1, 16),
            ('namespace n {}\nconst A: i32 = n::x', '`x` not found in namespace `n`', 2, 19),
            ('struct S { a: i32 }\nconst A: i32 = S::x', '`S` has no member `x`', 2, 19),
            ('fn f {} -> i32 { return 1 }\nconst A: i32 = f{}', 'a const cannot call a function', 2, 17),
            ('fn f {} {}\nconst A: fn{} = f', 'a const may only refer to other consts', 2, 17),
            ('const A: i32 = @as(i32, 1)', '@as is not allowed in a const', 1, 16),
            ('const A: []mut u8 = "x"', 'a string literal is read-only; it cannot be a []mut u8', 1, 21),
            ('const A: bool = 1 == null', 'only an optional can be compared with null, got {integer}', 1, 19),
            ('const A: i32 = 1 + 1.5', 'operands of `+` have incompatible types: {integer} and {float}; convert one with @as', 1, 18),
            ('const A: i32 = 1 << true', 'a shift count must be an integer, got bool', 1, 18),
            ('const A: bool = not 1', 'expected bool, got {integer}', 1, 21),
            ('const A: i32 = -true', 'unary `-` needs a number, got bool', 1, 16),
            ('const A: bool = true < false', '`<` needs numbers, got bool', 1, 22),
            ('union U(T) { a, b{ x: T } }\nconst A: bool = U::a == U::a', 'U(_) has no built-in equality', 2, 22),
            ('const A: i32 = 1.5', 'expected i32, got {float}', 1, 16),
            ('const A: [3]u8 = [7; 4]', 'expected [3]u8, got [4]u8', 1, 18),
            ('struct S { a: i32 }\nconst A: S = S{ .. }', '`..` is not allowed in a literal', 2, 15),
            ('const A: u8 = N\nconst N: i64 = 3', 'expected u8, got i64', 1, 15),
            ('const A: utf8::String = "\\xff"', 'string literal is not valid UTF-8 (byte 0)', 1, 25),
        ]:
            self.assertConstError(src + '\nfn main {} {}', msg, line, col)

    def test_inferred(self):
        for src in [
            'const A: [0]u8 = []',
            'struct P(T) { a: T }\nconst A: P(u8) = P{ a = 1 }',
            'const A: u64 = @size_of(u32) * 2',
            'union U(T) { a, b{ x: T } }\nconst A: U(u8) = U::b{ x = 1 }',
            'const A: ?u8 = 5',
            'const A: ?[]u8 = "x"',
            'const A: f32 = 1.5',
            'const A: [3]u8 = [7; 3]',
            'const A: usize = N\nconst N: u8 = 3',
            'const A: i64 = N\nconst N: u8 = 3',
            'const A: utf8::String = "ok"',
            'const A: bool = false and 1 / 0 == 1',
            'const A: i32 = -2147483648 % -1',
            'const A: i8 = 64 << 1',
        ]:
            run(src + '\nfn main {} {}')

    def test_folding(self):
        """A const's value is computed at compile time (§14): what would panic at run time is a
        compile error at the operation."""
        for src, msg, line, col in [
            ('const A: i32 = 2147483647 + 1', 'integer overflow in constant', 1, 27),
            ('const A: u32 = 5\nconst B: i64 = A * 3000000000', 'integer overflow in constant', 2, 18),
            ('const A: [1]u8 = [200 + 100]', 'integer overflow in constant', 1, 23),
            ('const A: i32 = 1 / 0', 'division by zero in constant', 1, 18),
            ('const A: u8 = 1 << 8', 'shift count out of range in constant', 1, 17),
            ('const A: i8 = -(-128)', 'integer overflow in constant', 1, 15),
            ('const A: i32 = B\nconst B: i32 = A', 'const `A` refers to itself', 2, 16),
            ('const A: i64 = -9223372036854775807 - 1 - 1', 'integer overflow in constant', 1, 41),
            ('const A: i32 = -2147483648 / -1', 'integer overflow in constant', 1, 28),
            ('const A: u8 = 3 - 4', 'integer overflow in constant', 1, 17),
            ('const A: i32 = 5 % 0', 'division by zero in constant', 1, 18),
            ('const A: i64 = 1 >> 64', 'shift count out of range in constant', 1, 18),
        ]:
            self.assertConstError(src + '\nfn main {} {}', msg, line, col)

    def test_non_finite(self):
        """A float const may fold to an infinity or a NaN, which no literal can be."""
        self.assertOutput("""
const G: f64 = 1.0 / 0.0
const M: f32 = -1.0 / 0.0
const N: f64 = 0.0 / 0.0
const A: [2]f64 = [G, N]
fn main { mut io: Io } {
    io::println_f64{ &io, n = G }
    io::println_f32{ &io, n = M }
    io::println_f64{ &io, n = N }
    io::println_f64{ &io, n = A[0] }
}
""", "inf\n-inf\nnan\ninf\n")

    def test_values(self):
        """Folded values reach the program: a const's uses read what the checker computed."""
        self.assertOutput("""
struct P { a: u64, b: ?u8 }
const N: u8 = 200
const M: u64 = 1000000
const W: u64 = M * 5000000 + N
const F: f32 = 1.1 * 3.0
const H: i32 = -7 / 2 + (-7 % 2) + (1 << 30) + (-8 >> 1)
const K: i8 = 64 << 1
const Q: P = P{ b = N - 1, a = W }
const Z: [4]i64 = [N; 4]
fn main { mut io: Io } {
    io::println_u64{ &io, n = W }
    io::println_f64{ &io, n = F }
    io::println_i64{ &io, n = H }
    io::println_i64{ &io, n = K }
    io::println_u64{ &io, n = Q.a }
    let b = Q.b
    if b != null { io::println_u64{ &io, n = b } }
    io::println_i64{ &io, n = Z[3] }
}
""", "5000000000200\n3.3000001907348633\n1073741816\n-128\n5000000000200\n199\n200\n")


class Bodies(Base):
    """Function bodies, the ctxc checker's sub-step 3: every error of statements, expressions,
    calls, binds, `match`, `let ... else` and narrowing at its exact position, for
    tools/checktest.py through the corpus. Definite initialization (sub-step 4) and
    exclusivity, escape and bound-function scope (sub-step 5) are tested elsewhere."""

    def assertBodyError(self, src, msg, line, col):
        with self.assertRaises(CompileError) as cm:
            run(src)
        self.assertEqual((cm.exception.msg, cm.exception.pos[:2]), (msg, (line, col)), src)

    def test_errors(self):
        U2 = 'union U { a, b{ x: i32 } }\n'
        U3 = 'union U { a, b{ x: i32 }, c{ x: i32, y: bool } }\n'
        B = 'fn w { mut b: utf8::Builder(arena::Arena) } -> bool {\n'
        for src, msg, line, col in [
            ('fn f {} {\n    let x = null\n}',
             'cannot infer the type of `null` here; add a type', 2, 13),
            ('fn g {} {}\nfn f {} {\n    let x = g{}\n}',
             'expression has no value', 3, 14),
            ('fn f {} {\n    let x = 1\n    if true {\n        let y = 2\n        let y = 3\n    }\n}',
             '`y` is already declared in this scope', 5, 9),
            ('fn f {} {\n    let x = 1\n    x = 2\n}',
             'cannot assign to `x`: it is read-only', 3, 5),
            (U2 + 'fn f { u: *U } {\n    match u {\n        a => {}\n        b{ &x } => { x = 2 }\n    }\n}',
             'cannot assign to `x`: it is bound through a read-only pointer', 5, 22),
            ('fn f {} {\n    let mut x: i32 = 0\n    x = true\n}',
             'expected i32, got bool', 3, 9),
            ('fn f {} {\n    let x = 1\n    x + 1\n}',
             'an expression statement must be a call', 3, 7),
            ('struct S { a: i32 }\nfn f {} {\n    S{ a = 1 }\n}',
             'an expression statement must be a call', 3, 6),
            ('fn g {} -> i32 { return 1 }\nfn f {} {\n    g{}\n}',
             'the result of `g` (i32) is unused: use it, or discard it with `_ = ...`', 3, 6),
            ('fn g {} {}\nfn f {} {\n    _ = g{}\n}',
             'nothing to discard: this returns no value', 3, 10),
            ('fn f {} -> i32 {\n    return\n}',
             '`return` needs a value here', 2, 5),
            ('fn f {} {\n    return 1\n}',
             'this function has no return type', 2, 5),
            ('fn f {} {\n    defer { return }\n}',
             'cannot `return` from a defer', 2, 13),
            ('fn f { c: bool } -> i32 {\n    if c { return 1 }\n}',
             '`f` must end every path in `return` or `@panic()`', 1, 1),
            ('fn f {} {\n    outer: while true {\n        outer: while true { break }\n    }\n}',
             'loop label `outer` is already used by an enclosing loop', 3, 9),
            ('fn f {} {\n    break\n}',
             '`break` outside a loop', 2, 5),
            ('fn f {} {\n    while true {\n        defer { continue }\n        break\n    }\n}',
             '`continue` outside a loop in this defer', 3, 17),
            ('fn f {} {\n    while true {\n        break inner\n    }\n}',
             'no enclosing loop is labeled `inner`', 3, 9),
            ('fn g {} {}\nfn f { c: bool } -> i32 {\n    let x = if c { g{} } else { 1 }\n    return x\n}',
             'this branch has no value: its last expression returns nothing', 3, 21),
            ('fn f { c: bool } -> i32 {\n    let x = if c { let y = 1 } else { 2 }\n    return x\n}',
             'this branch must end in a value, or leave with `return`, `break`, `continue` or `@panic()`', 2, 18),
            ('fn f { c: bool } -> i32 {\n    while true {\n        let x = if c { break } else { continue }\n    }\n    return 1\n}',
             'no branch of this expression produces a value; use a statement instead', 3, 17),
            ('fn f { c: bool } -> i32 {\n    let x = if c { 1 } else { true }\n    return x\n}',
             'branches have different types: {integer} and bool', 2, 13),
            ('enum E: u8 { a, b }\nfn f { e: *E } {\n    match e {\n        a => {}\n        b => {}\n    }\n}',
             'match cannot go through a pointer to an enum; match on the value with `.*`', 3, 11),
            ('fn f { n: i32 } {\n    match n {\n        a => {}\n    }\n}',
             'match needs a union, enum or optional value, got i32', 2, 11),
            (U2 + 'fn f { u: U } {\n    match u {\n        else => {}\n        a => {}\n    }\n}',
             '`else` must be the last arm', 4, 9),
            (U2 + 'fn f { u: U } {\n    match u {\n        a => {}\n        b => {}\n        else => {}\n    }\n}',
             '`else` is unreachable: every variant is already listed', 6, 9),
            (U2 + 'fn f { u: U } {\n    match u {\n        a => {}\n        z => {}\n    }\n}',
             'U has no variant `z`', 5, 9),
            (U2 + 'fn f { u: U } {\n    match u {\n        a => {}\n        a | b => {}\n    }\n}',
             'variant `a` appears in more than one arm', 5, 9),
            (U3 + 'fn f { u: U } {\n    match u {\n        b => {}\n    }\n}',
             "match isn't exhaustive: missing a, c", 3, 5),
            (U2 + 'fn f { u: U } {\n    match u {\n        a{ x } => {}\n        b => {}\n    }\n}',
             'variant `a` has no payload', 4, 9),
            (U2 + 'fn f { u: U } {\n    match u {\n        a => {}\n        b{ z } => {}\n    }\n}',
             'variant `b` has no field `z`', 5, 12),
            (U2 + 'fn f { u: U } {\n    match u {\n        a => {}\n        b{ x, x = y } => {}\n    }\n}',
             '`x` is bound twice', 5, 15),
            (U2 + 'fn f { u: U } {\n    match u {\n        a => {}\n        b{ &x } => {}\n    }\n}',
             '`&x` needs a pointer scrutinee', 5, 12),
            (U3 + 'fn f { u: U } {\n    match u {\n        a => {}\n        b{ x } | c{ y } => {}\n    }\n}',
             '`c` must bind `x`, as `b` in the same arm does', 5, 18),
            (U3 + 'fn f { u: U } {\n    match u {\n        a => {}\n        b{ x } | c{ y = x } => {}\n    }\n}',
             '`x` is i32 in `b` but bool in `c`', 5, 21),
            (U3 + 'fn f { u: *mut U } {\n    match u {\n        a => {}\n        b{ &x } | c{ x } => {}\n    }\n}',
             '`x` must be bound with `&` in both `b` and `c`, or in neither', 5, 22),
            (U3 + 'fn f { u: U } {\n    match u {\n        a => {}\n        b{ x } | c{ x, y } => {}\n    }\n}',
             '`c` binds `y`, which `b` in the same arm does not', 5, 24),
            (U2 + 'fn f { u: *U } {\n    let b{ x } = u else { return }\n}',
             'a `let` pattern cannot match through a pointer; use `match`', 3, 18),
            ('fn f { n: i32 } {\n    let a = n else { return }\n}',
             'a `let` pattern needs a union or optional value, got i32', 2, 13),
            (U2 + 'fn f { u: U } {\n    let z{ x } = u else { return }\n}',
             'U has no variant `z`', 3, 5),
            (U2 + 'fn f { u: U } {\n    let b{ x } = u else z { return }\n}',
             'U has no variant `z`', 3, 27),
            (U2 + 'fn f { u: U } {\n    let b{ x } = u else b { return }\n}',
             'variant `b` appears on both sides of the `else`', 3, 27),
            ('union U { a, b{ x: i32 }, c }\nfn f { u: U } {\n    let b{ x } = u else a { return }\n}',
             '`else a` would skip c; a pattern after `else` must name the only other variant', 3, 27),
            (U2 + 'fn f { u: U } {\n    let b{ x } = u else {\n        let y = 1\n    }\n}',
             'the `else` of a `let` pattern must leave: end it with `return`, `break`, `continue` or `@panic()`', 3, 25),
            ('fn f {} {\n    let x = y\n}',
             'unknown name `y`', 2, 13),
            ('fn f {} {\n    let x = 1\n    let y = x(i32)\n}',
             '`x` is not generic', 3, 13),
            ('fn f {} {\n    let x = 1\n    x{}\n}',
             '`x` has type {integer} and cannot be called', 3, 5),
            ('const C: i32 = 1\nfn f {} {\n    _ = C{}\n}',
             '`C` has type i32 and cannot be called', 3, 9),
            ('fn g { a: i32, b: i32 } {}\nfn f {} {\n    g{}\n}',
             'call to `g` is missing `a`, `b`', 3, 6),
            ('fn g { a: i32, b: i32 } {}\nfn f {} {\n    g{ a = 1, b = 2, z = 3 }\n}',
             '`g` has no field `z`', 3, 22),
            ('fn g { a: i32, b: i32 } {}\nfn f {} {\n    g{ a = 1, a = 2, b = 3 }\n}',
             '`a` is supplied more than once', 3, 15),
            ('fn g { a: i32, n: i32 } {}\nfn f { a: i32 } {\n    g{ .. }\n}',
             '`..` cannot supply `n`: no local or context field named `n`', 3, 6),
            ('fn g { a: i32, b: i32 } {}\nfn f {} {\n    let h: fn{ a: i32 } = g\n}',
             "function needs `b`, which fn{ a: i32 } doesn't provide", 3, 27),
            ('fn g { mut a: i32 } {}\nfn f { p: *i32 } {\n    g{ a = p }\n}',
             'expected *mut i32, got *i32', 3, 12),
            ('fn g { mut a: i32 } {}\nfn f {} {\n    let x = 1\n    g{ a = &x }\n}',
             '`x` is not a mutable place', 4, 13),
            ('fn f { p: *i32 } {\n    p.* = 1\n}',
             'cannot write through *i32; it needs to be a `*mut`', 2, 6),
            ('fn f { s: []i32 } {\n    s[0] = 1\n}',
             'cannot write through []i32; it needs to be a `[]mut`', 2, 6),
            ('const C: i32 = 1\nfn f {} {\n    let p = &C\n}',
             '`C` is a const, not a place', 3, 14),
            ('fn g {} {}\nfn f {} {\n    let p = &g\n}',
             '`g` is not a place', 3, 14),
            ('fn f { a: [2]i32 } {\n    let p = &a.len\n}',
             '`.len` is not a place', 2, 15),
            ('fn f {} {\n    let p = &(1 + 2)\n}',
             'expression is not a place', 2, 17),
            ('fn f {} {\n    let x = 1\n    let y = x.f\n}',
             'the type of this expression must be known before `.f`', 3, 14),
            ('struct S { a: i32 }\nfn f { s: S } {\n    let y = s.b\n}',
             'S has no field `b`', 3, 14),
            ('fn f { p: *i32 } {\n    let y = p.b\n}',
             '*i32 has no field `b`', 2, 14),
            ('fn f(T) { x: T } {\n    let y = x.b\n}',
             'T has no field `b`', 2, 14),
            ('fn f { n: i32 } {\n    let y = n.*\n}',
             '`.*` needs a pointer, got i32', 2, 14),
            ('fn f { n: i32 } {\n    let y = n[0]\n}',
             'cannot index i32', 2, 14),
            ('fn f { n: i32 } {\n    let y = n[0..1]\n}',
             'cannot slice i32', 2, 14),
            ('fn f { p: *i32 } {\n    let q = p - 1\n}',
             '`-` is not defined on pointers', 2, 15),
            ('fn f {} {\n    let m = "x"\n    @panic(m)\n}',
             '@panic takes a string literal', 3, 12),
            ('enum E: u8 { a }\nfn f {} {\n    let e = @as(E, true)\n}',
             '@as to an enum takes an integer, got bool', 3, 20),
            ('enum E: u8 { a }\nfn f { e: E } {\n    let n = @as(bool, e)\n}',
             '@as converts an enum to an integer type, not bool', 3, 13),
            ('fn f {} {\n    let n = @as(bool, 1)\n}',
             '@as needs a numeric target type, got bool', 2, 13),
            ('fn f {} {\n    let n = @as(i32, true)\n}',
             '@as converts numbers only', 2, 22),
            ('fn f {} {\n    let n = @trunc(bool, 1)\n}',
             '@trunc needs an integer target type, got bool', 2, 13),
            ('fn f {} {\n    let n = @trunc(u8, 1.5)\n}',
             '@trunc converts integers only', 2, 24),
            ('fn f { p: *i32 } {\n    let q = @cast(i32, p)\n}',
             '@cast needs a pointer or extern fn target type, got i32', 2, 13),
            ('fn f { n: i32 } {\n    let q = @cast(*u8, n)\n}',
             '@cast needs a pointer or extern fn argument', 2, 24),
            ('fn f { p: *i32 } {\n    let q = @cast(*mut u8, p)\n}',
             '@cast cannot make *i32 writable', 2, 28),
            ('fn f { n: i32 } {\n    let s = @slice(n, 1)\n}',
             '@slice needs a pointer, got i32', 2, 20),
            ('fn f { n: i32 } {\n    let a = @addr(n)\n}',
             '@addr needs a pointer argument', 2, 19),
            ('fn f { a: i32, b: i64 } {\n    let c = @wrap_add(a, b)\n}',
             '@wrap_add needs two integers of the same type', 2, 13),
            ('fn w { mut bs: [1]utf8::Builder(arena::Arena) } -> bool {\n    return @fmt(&bs[0], "x")\n}',
             '@fmt takes its builder as `&b`, `&x.f` or a name: it is used once per piece', 2, 17),
            ('fn w { mut n: i32 } -> bool {\n    return @fmt(&n, "x")\n}',
             '@fmt writes to a *mut utf8::Builder, got *mut i32', 2, 17),
            (B + '    let s = "x"\n    return @fmt(&b, s)\n}',
             '@fmt takes its format as a string literal', 3, 21),
            (B + '    return @fmt(&b, "a{", 1)\n}',
             'the format has a `{` without a `}`; write `{{` for a brace', 2, 21),
            (B + '    return @fmt(&b, "a}")\n}',
             'the format has a `}` without a `{`; write `}}` for a brace', 2, 21),
            (B + '    return @fmt(&b, "{q}", 1)\n}',
             'bad hole `{q}` in the format: use `{}`, `{x}`, `{c}` or a width such as `{8}` or `{08x}`', 2, 21),
            (B + '    return @fmt(&b, "{} {}", 1)\n}',
             'the format has 2 holes but 1 argument follows it', 2, 12),
            (B + '    return @fmt(&b, "{}")\n}',
             'the format has 1 hole but 0 arguments follow it', 2, 12),
            (B + '    return @fmt(&b, "x", 1, 2)\n}',
             'the format has 0 holes but 2 arguments follow it', 2, 12),
            (B + '    return @fmt(&b, "{5c}", 65)\n}',
             '`{5c}`: a width applies to numbers and text, not characters', 2, 29),
            (B + '    let n: i32 = 1\n    return @fmt(&b, "{x}", n)\n}',
             '`{x}` formats an unsigned integer, not i32', 3, 28),
            (B + '    return @fmt(&b, "{5}", true)\n}',
             '`{5}`: a width applies to integers and utf8::String, not bool', 2, 28),
            ('struct S { a: i32 }\n' + B + '    return @fmt(&b, "{}", S{ a = 1 })\n}',
             "@fmt can't format S: give a utf8::String, a number, a bool, an error, or a function that writes to the builder", 3, 28),
            (B + '    let n: i64 = 65\n    return @fmt(&b, "{c}", n)\n}',
             'expected u32, got i64', 3, 28),
            ('fn wr { mut b: i32 } -> bool { return true }\n' + B + '    return @fmt(&b, "{}", wr)\n}',
             'expected *mut i32, got *mut utf8::Builder(arena::Arena)', 3, 17),
            ('struct S { f: i32 }\nfn f { o: ?S } {\n    let y = o.f\n}',
             '?S has no field `f`', 3, 14),
            ('struct S { f: i32 }\nfn f {} {\n    let mut x: ?S = null\n    if x == null { return }\n    let y = x.f\n}',
             '?S has no field `f`', 5, 14),
            ('fn f { n: i32 } {\n    if n == null { return }\n}',
             'only an optional can be compared with null, got i32', 2, 10),
            ('fn f {} {\n    while true {\n        defer { break }\n    }\n}',
             '`break` outside a loop in this defer', 3, 17),
            ('fn f {} {\n    outer: while true {\n        defer {\n            while true { break outer }\n        }\n        break\n    }\n}',
             'no enclosing loop is labeled `outer` in this defer', 4, 26),
            ('fn g { mut a: i32 } {}\n' + U2 + 'fn f { u: *U } {\n    match u {\n        a => {}\n        b{ &x } => { g{ a = &x } }\n    }\n}',
             '`x` is not a mutable place: it is bound through a read-only pointer', 6, 30),
            ('fn f(T) { u: ?T } -> T {\n    match u {\n        null => { return y }\n        some{ value } => { return value }\n    }\n}',
             'unknown name `y`', 3, 26),
            ('struct S { f: i32 }\nfn f { c: bool } {\n    let mut x: ?S = null\n    if c {\n        if x == null { return }\n        let y = x.f\n    }\n}',
             '?S has no field `f`', 6, 18),
        ]:
            self.assertBodyError(src + '\nfn main {} {}', msg, line, col)

    def test_checks(self):
        for src in [
            # narrowing: != null
            'fn f { o: ?i32 } -> i32 {\n    if o != null { return o + 1 }\n    return 0\n}\nfn main {} {\n    _ = f{ o = 1 }\n}',
            # == null with early return
            'fn f { o: ?i32 } -> i32 {\n    if o == null { return 0 }\n    return o * 2\n}\nfn main {} {\n    _ = f{ o = null }\n}',
            # and / or / not
            'fn f { a: ?i32, b: ?i32 } -> i32 {\n    if a != null and b != null { return a + b }\n    if a == null or b == null { return 0 }\n    return a - b\n}\nfn main {} {\n    _ = f{ a = 1, b = null }\n}',
            'fn f { a: ?i32 } -> i32 {\n    if not (a == null) { return a }\n    return 0\n}\nfn main {} {\n    _ = f{ a = 3 }\n}',
            # field paths
            'struct In { b: ?i32 }\nstruct Out { a: In }\nfn f { o: Out } -> i32 {\n    if o.a.b != null { return o.a.b }\n    return 0\n}\nfn main {} {\n    _ = f{ o = Out{ a = In{ b = 4 } } }\n}',
            # while condition
            'struct Node { next: ?*Node, v: i32 }\nfn sum { n: *Node } -> i32 {\n    let mut total = n.v\n    let mut p: ?*Node = n.next\n    while true {\n        let q = p\n        if q == null { break }\n        total = total + q.v\n        p = q.next\n    }\n    return total\n}\nfn main {} {\n    let c = Node{ next = null, v = 2 }\n    let a = Node{ next = &c, v = 1 }\n    _ = sum{ n = &a }\n}',
            'fn f { o: ?i32 } -> i32 {\n    let mut n = 0\n    while o != null and n < o { n = n + 1 }\n    return n\n}\nfn main {} {\n    _ = f{ o = 3 }\n}',
            # after an if whose branch returns (with else)
            'fn f { o: ?i32, c: bool } -> i32 {\n    if o == null {\n        return 0\n    } else if c {\n        return 1\n    }\n    return o\n}\nfn main {} {\n    _ = f{ o = 5, c = false }\n}',
            # if expression with null making ?T
            'fn f { c: bool } -> ?i32 {\n    let x = if c { 1 } else { null }\n    return x\n}\nfn main {} {\n    _ = f{ c = true }\n}',
            # string literal branches as views next to a utf8::String
            'fn name { c: bool, s: utf8::String } -> utf8::String {\n    return if c { s } else { "none" }\n}\nfn main {} {\n    _ = name{ c = false, s = "x" }\n}',
            'union P { anon, named{ n: utf8::String } }\nfn name { p: P } -> utf8::String {\n    let s = match p {\n        anon => { "anonymous" }\n        named{ n } => { n }\n    }\n    return s\n}\nfn main {} {\n    _ = name{ p = P::anon }\n}',
            # nested else if
            'fn sign { n: i32 } -> i32 {\n    return if n < 0 { -1 } else if n == 0 { 0 } else { 1 }\n}\nfn main {} {\n    _ = sign{ n = -5 }\n}',
            # branches that return
            'fn f { o: ?i32 } -> i32 {\n    let x = if o != null { o } else { return 0 }\n    return x\n}\nfn main {} {\n    _ = f{ o = 2 }\n}',
            'union U { a, b{ x: i32 } }\nfn f { u: U } -> i32 {\n    let x = match u {\n        a => { @panic("no") }\n        b{ x } => { x }\n    }\n    return x\n}\nfn main {} {\n    _ = f{ u = U::b{ x = 1 } }\n}',
            # let-else without and with else pattern
            'union U { a, b{ x: i32 } }\nfn f { u: U } -> i32 {\n    let b{ x } = u else { return 0 }\n    return x\n}\nfn main {} {\n    _ = f{ u = U::a }\n}',
            'union R { ok{ v: i32 }, err{ code: i32 } }\nfn f { r: R } -> i32 {\n    let ok{ v } = r else err{ code } {\n        return code\n    }\n    return v\n}\nfn main {} {\n    _ = f{ r = R::err{ code = 2 } }\n}',
            'fn f { o: ?i32 } -> i32 {\n    let some{ value = n } = o else null { return 0 }\n    return n\n}\nfn main {} {\n    _ = f{ o = 7 }\n}',
            # labeled loops
            'fn f {} -> i32 {\n    let mut n = 0\n    let mut i = 0\n    outer: while i < 5 {\n        i = i + 1\n        let mut j = 0\n        while j < 5 {\n            j = j + 1\n            if j == 2 { continue outer }\n            if i == 4 { break outer }\n            n = n + 1\n        }\n    }\n    return n\n}\nfn main {} {\n    _ = f{}\n}',
            # defer
            'fn f { mut n: i32 } {\n    defer n = n + 1\n    defer {\n        n = n * 2\n    }\n    n = 3\n}\nfn main {} {\n    let mut n = 0\n    f{ &n }\n}',
            # binds and calling them
            'fn add { a: i32, b: i32 } -> i32 { return a + b }\nfn main {} {\n    let inc = add{ a = 1, _ }\n    _ = inc{ b = 2 }\n    let g: &fn{ b: i32 } -> i32 = inc\n    _ = g{ b = 3 }\n}',
            # function values
            'fn twice { f: fn{ n: i32 } -> i32, n: i32 } -> i32 { return f{ n = f{ n } } }\nfn inc { n: i32 } -> i32 { return n + 1 }\nfn main {} {\n    _ = twice{ f = inc, n = 1 }\n}',
            # .. forwarding including a mut field
            'fn bump { mut n: i32, by: i32 } { n = n + by }\nfn main {} {\n    let mut n = 0\n    let by = 2\n    bump{ .. }\n    bump{ by = 3, .. }\n}',
            # & of fields and array elements
            'struct P { x: i32, y: i32 }\nfn set { mut n: i32 } { n = 1 }\nfn main {} {\n    let mut p = P{ x = 0, y = 0 }\n    let mut a: [3]i32 = [0, 0, 0]\n    set{ n = &p.y }\n    set{ n = &a[2] }\n    let q = &p.x\n    _ = q.*\n}',
            # ranges on arrays, slices, pointers to arrays
            'fn total { s: []i32 } -> i32 {\n    let mut t = 0\n    let mut i: usize = 0\n    while i < s.len {\n        t = t + s[i]\n        i = i + 1\n    }\n    return t\n}\nfn main {} {\n    let a: [4]i32 = [1, 2, 3, 4]\n    let s = a[1..3]\n    let p = &a\n    _ = total{ s = s[..1] }\n    _ = total{ s = p[2..] }\n    _ = total{ s = a[..] }\n}',
            'fn main {} {\n    let mut a: [4]u8 = [0; 4]\n    let s = a[0..2]\n    s[1] = 7\n    let p = &a\n    p[3] = 1\n    _ = p.len\n}',
            # ptr arithmetic
            'fn main {} {\n    let a: [3]i32 = [1, 2, 3]\n    let p = @cast(*i32, &a)\n    let q = p + 2\n    _ = q.* + p[1]\n}',
            # builtins
            'enum E: u8 { a, b }\nfn main {} {\n    let n: i64 = 300\n    let x = @as(f64, n)\n    let y = @trunc(u8, n)\n    let e = @as(E, 1)\n    let k = @as(u32, e)\n    let w = @wrap_add(y, @as(u8, 250))\n    let v = @wrap_sub(y, w)\n    let m = @wrap_mul(y, v)\n    let s = @size_of(i64) + @align_of(u32)\n    let mut arr: [4]u8 = [0; 4]\n    let sl = @slice(&arr[0], 2)\n    sl[0] = 1\n    let addr = @addr(&arr)\n    let bp = @cast(*u8, &arr)\n    _ = addr + s + @as(usize, m) + @as(usize, k) + @as(usize, bp.*)\n    _ = x\n}',
            'fn f { n: i32 } -> i32 {\n    if n < 0 { @panic("negative") }\n    if n > 100 { @panic() }\n    return n\n}\nfn main {} {\n    _ = f{ n = 1 }\n}',
            # @fmt with widths, x, c and function holes
            'struct D { y: u32 }\nfn w_d { mut b: utf8::Builder(arena::Arena), d: D } -> bool {\n    return @fmt(&b, "{04}", d.y)\n}\nfn main {} {\n    let mut mem: [256]u8\n    let mut heap = arena::new{ buf = mem[..] }\n    let mut b = utf8::builder{ realloc = arena::alloc, &heap }\n    let d = D{ y = 7 }\n    let name: utf8::String = "ab"\n    _ = @fmt(&b, "[{5}] {x} {08x} {c} {6} {} {} {{}}", 42, 255, 48879, 65, name, true, w_d{ d, _ })\n}',
            # generic functions with inferred args
            'fn first(T) { a: T, b: T } -> T { return a }\nfn wrap(T) { v: T } -> ?T { return v }\nfn main {} {\n    let x: i64 = first{ a = 1, b = 2 }\n    let o = wrap{ v = true }\n    if o != null { _ = first{ a = o, b = false } }\n    _ = x\n}',
            # match through *mut U with &f binders
            'union U { a, b{ x: i32, y: i32 } }\nfn bump { u: *mut U } {\n    match u {\n        a => {}\n        b{ &x, y } => { x = x + y }\n    }\n}\nfn main {} {\n    let mut u = U::b{ x = 1, y = 2 }\n    bump{ u = &u }\n}',
            # alternatives binding the same field
            'union U { a{ n: i32 }, b{ n: i32 }, c }\nfn f { u: U } -> i32 {\n    return match u {\n        a{ n } | b{ n } => { n }\n        c => { 0 }\n    }\n}\nfn main {} {\n    _ = f{ u = U::c }\n}',
            # enums in match
            'enum Dir: u8 { n, e, s, w }\nfn turn { d: Dir } -> Dir {\n    return match d {\n        n => { Dir::e }\n        e => { Dir::s }\n        s => { Dir::w }\n        else => { Dir::n }\n    }\n}\nfn main {} {\n    let d = turn{ d = Dir::w }\n    match d {\n        n | s => {}\n        e | w => {}\n    }\n}',
            # optional match
            'fn f { o: ?i32 } -> i32 {\n    match o {\n        null => { return 0 }\n        some{ value } => { return value }\n    }\n}\nfn main {} {\n    _ = f{ o = null }\n}',
            # assignments to fields and through pointers
            'struct P { x: i32 }\nfn set { p: *mut P } { p.x = 3 }\nfn main {} {\n    let mut p = P{ x = 0 }\n    set{ p = &p }\n    let q = &p\n    q.*.x = 4\n    q.* = P{ x = 5 }\n}',
            # shadowing in an inner scope and discards
            'fn g {} -> i32 { return 1 }\nfn main {} {\n    let x = 1\n    if true {\n        let x = true\n        _ = x\n    }\n    _ = g{} + x\n}',
        ]:
            run(src)


class Initialization(Base):
    """Definite initialization (§11), the ctxc checker's sub-step 4: every error at its exact
    position, for tools/checktest.py through the corpus."""

    def assertInitError(self, src, msg, line, col):
        with self.assertRaises(CompileError) as cm:
            run(src)
        self.assertEqual((cm.exception.msg, cm.exception.pos[:2]), (msg, (line, col)), src)

    def test_errors(self):
        READ = '`x` may be read before it is assigned'
        TWICE = '`x` may be assigned more than once'
        LOOP = TWICE + ': it is assigned in a loop that can repeat; declare it with `let mut`'
        DEFER = 'cannot assign `x` in a defer: declare it with `let mut`'
        for src, msg, line, col in [
            ('fn f {} -> i32 {\n    let x: i32\n    return x\n}', READ, 3, 12),
            ('fn f { c: bool } -> i32 {\n    let x: i32\n    if c { x = 1 }\n    return x\n}', READ, 4, 12),
            ('fn f { c: bool } -> i32 {\n    let mut x: *i32\n    let y = 1\n    if c { x = &y }\n    return x.*\n}', READ, 5, 12),
            ('fn f { c: bool } -> i32 {\n    let x: i32\n    while c { x = 1; break }\n    return x\n}', READ, 4, 12),
            ('fn f {} {\n    let g: fn{}\n    g{}\n}', '`g` may be read before it is assigned', 3, 5),
            ('fn g { n: i32 } {}\nfn f {} {\n    let n: i32\n    g{ .. }\n}', '`n` may be read before it is assigned', 4, 6),
            ('fn f {} -> i32 {\n    let x: ?i32\n    if x == null { return 0 }\n    return x\n}', READ, 3, 8),
            ('fn f {} {\n    let x: i32\n    x = 1\n    x = 2\n}', TWICE, 4, 5),
            ('fn f { c: bool } {\n    let x: i32\n    if c { x = 1 }\n    x = 2\n}', TWICE, 4, 5),
            ('fn f { c: bool } -> i32 {\n    let x: i32\n    let some{ value } = if c { 1 } else { null } else { x = 0; return x }\n    x = value\n    return x\n}', TWICE, 4, 5),
            ('fn f { c: bool } {\n    let x: i32\n    while c {\n        x = 1\n    }\n}', LOOP, 3, 5),
            ('fn f { c: bool } {\n    let x: i32\n    while c {\n        if c { x = 1; continue }\n        break\n    }\n}', LOOP, 3, 5),
            ('fn f { c: bool } -> i32 {\n    let x: i32\n    while true {\n        if c { x = 1; break }\n    }\n    return x\n}', LOOP, 3, 5),
            ('fn f {} {\n    let x: i32\n    defer x = 1\n    x = 2\n}', DEFER, 3, 5),
            ('fn f {} {\n    let x: i32\n    defer { if true { x = 1 } }\n    x = 2\n}', DEFER, 3, 5),
        ]:
            self.assertInitError(src + '\nfn main {} {}', msg, line, col)

    def test_checks(self):
        for src in [
            'fn f { c: bool } -> i32 {\n    let x: i32\n    if c { x = 1 } else { x = 2 }\n    return x\n}',
            'fn f { c: bool } -> i32 {\n    let x: i32\n    if c { return 0 }\n    x = 3\n    return x\n}',
            'fn f { c: bool } -> i32 {\n    let x: i32\n    while true {\n        x = 1\n        break\n    }\n    return x\n}',
            'fn f { c: bool } -> i32 {\n    let mut x: i32\n    while c { x = x + 1 }\n    return x\n}',
            'fn f { c: bool } -> i32 {\n    let x: i32\n    while c {\n        let y: i32\n        y = 1\n        if y > 0 { break }\n    }\n    x = 1\n    return x\n}',
            'union U { a{ n: i32 }, b }\nfn f { u: U } -> i32 {\n    let x: i32\n    match u {\n        a{ n } => { x = n }\n        b => { x = 0 }\n    }\n    return x\n}',
            'fn f {} -> i32 {\n    let mut x: ?i32\n    defer x = 1\n    return 0\n}',
            'fn f { c: bool } -> i32 {\n    let x: i32\n    let y = if c { x = 1; 2 } else { x = 3; 4 }\n    return x + y\n}',
            'fn f { c: bool } -> i32 {\n    let x: i32\n    if c { x = 1 } else { @panic() }\n    return x\n}',
        ]:
            run(src + '\nfn main {} {}')


class Safety(Base):
    """Exclusivity (§3.1), escape analysis (§14) and bound-function scope (§6), the ctxc
    checker's sub-step 5: every error at its exact position, for tools/checktest.py through the
    corpus. Where a value is derived from several locals, the message names the first declared."""

    def assertSafetyError(self, src, msg, line, col):
        with self.assertRaises(CompileError) as cm:
            run(src)
        self.assertEqual((cm.exception.msg, cm.exception.pos[:2]), (msg, (line, col)), src)

    def test_errors(self):
        for src, msg, line, col in [
            ('struct P { a: i32, b: i32 }\nfn g { mut x: i32, mut y: i32 } {}\nfn f {} {\n    let mut p = P{ a = 1, b = 2 }\n    g{ x = &p.a, y = &p.a }\n}',
             'two mut references to `p.a` in one call', 5, 6),
            ('fn g { mut x: [2]i32, mut y: i32 } {}\nfn f {} {\n    let mut a = [1, 2]\n    g{ x = &a, y = &a[1] }\n}',
             'two mut references to `a` in one call', 4, 6),
            ('fn g { mut x: i32, mut y: i32 } {}\nfn f { mut x: i32 } {\n    g{ &x, y = &x }\n}',
             'two mut references to `x` in one call', 3, 6),
            ('fn g { mut x: i32, mut y: i32 } {}\nfn f { mut x: i32, mut y: i32 } {\n    g{ &x, .. }\n    g{ y = &x, .. }\n}',
             'two mut references to `x` in one call', 4, 6),
            ('fn inc { mut n: i32 } { n = n + 1 }\nfn g { mut n: i32, f: &fn{} } {}\nfn f {} {\n    let mut n = 0\n    let h = inc{ &n, _ }\n    g{ &n, f = h }\n}',
             '`n` overlaps a place held by `h`', 6, 6),
            ('fn inc { mut n: i32 } { n = n + 1 }\nfn g { mut n: i32, h: &fn{} } {}\nfn f {} {\n    let mut n = 0\n    let h = inc{ &n, _ }\n    g{ &n, .. }\n}',
             '`n` overlaps a place held by `h`', 6, 6),
            ('fn inc { mut n: i32 } { n = n + 1 }\nfn g { mut n: i32, f: &fn{} } {}\nfn f {} {\n    let mut n = 0\n    g{ &n, f = inc{ &n, _ } }\n}',
             '`n` overlaps a place held by `f`', 5, 6),
            ('fn two { mut a: i32, mut b: i32 } {}\nfn f {} {\n    let mut n = 0\n    let h = two{ a = &n, b = &n, _ }\n}',
             'two mut references to `n` in one call', 4, 16),
            ('union U { a{ x: i32 }, b }\nfn f { mut u: U } {\n    match &u {\n        a{ &x } => { u = U::b }\n        b => {}\n    }\n}',
             'u overlaps the match scrutinee; access it only through `x`', 4, 22),
            ('union U { a{ x: i32 }, b }\nfn g { u: U } {}\nfn f { mut u: U } {\n    match &u {\n        a => { g{ u = u } }\n        b => {}\n    }\n}',
             'u overlaps the match scrutinee; access it only through the arm bindings', 5, 23),
            ('union U { a{ x: i32 }, b }\nfn g { u: U } {}\nfn f { mut u: U } {\n    match &u {\n        a{ &x } => { g{ .. } }\n        b => {}\n    }\n}',
             'u overlaps the match scrutinee; access it only through `x`', 5, 23),
            ('struct S { u: U, n: i32 }\nunion U { a{ x: i32 }, b }\nfn f { mut s: S } {\n    match &s.u {\n        a{ &x } => { x = s.n; s.u = U::b }\n        b => {}\n    }\n}',
             's.u overlaps the match scrutinee; access it only through `x`', 5, 32),
            ('fn f {} -> *i32 {\n    let x = 1\n    return &x\n}',
             'returned value holds the address of local `x`', 3, 5),
            ('fn f { c: bool } -> *i32 {\n    let x = 1\n    let y = 2\n    let p = if c { &x } else { &y }\n    return p\n}',
             'returned value holds the address of local `x`', 5, 5),
            ('fn id { p: *i32 } -> *i32 { return p }\nfn f {} -> *i32 {\n    let x = 1\n    return id{ p = &x }\n}',
             'returned value holds the address of local `x`', 4, 5),
            ('fn f {} -> []i32 {\n    let a = [1, 2]\n    return a[..]\n}',
             'returned value holds the address of local `a`', 3, 5),
            ('fn f {} -> *u8 {\n    let a = [1, 2]\n    return @cast(*u8, &a) + 1\n}',
             'returned value holds the address of local `a`', 3, 5),
            ('fn f {} -> ?*i32 {\n    let x = 1\n    return &x\n}',
             'returned value holds the address of local `x`', 3, 5),
            ('fn f { x: i32 } -> *i32 {\n    return &x\n}',
             'returned value holds the address of local `x`', 2, 5),
            ('struct B { p: *i32 }\nfn f {} -> B {\n    let x = 1\n    return B{ p = &x }\n}',
             'returned value holds the address of local `x`', 4, 5),
            ('fn f { mut out: *i32 } {\n    let x = 1\n    out = &x\n}',
             'cannot store the address of local `x` in `out`, which belongs to the caller', 3, 5),
            ('fn f { q: *mut *i32 } {\n    let x = 1\n    q.* = &x\n}',
             'cannot store the address of local `x` through a pointer', 3, 5),
            ('fn f {} {\n    let mut p: *i32\n    let a = 1\n    p = &a\n    if true {\n        let x = 1\n        p = &x\n    }\n}',
             '`p` outlives local `x` whose address it would hold', 7, 9),
            ('fn f {} {\n    let a = 1\n    let mut p = &a\n    if true {\n        let x = 1\n        let q = &x\n        p = q\n    }\n}',
             '`p` outlives local `x` whose address it would hold', 7, 9),
            ('fn f { c: bool } -> i32 {\n    let y = 0\n    let p = if c { let x = 1; &x } else { &y }\n    return p.*\n}',
             'the value of this branch holds the address of local `x`, which ends with the branch', 3, 31),
            ('fn inc { mut n: i32 } { n = n + 1 }\nfn f { c: bool } {\n    let mut m = 0\n    let h = if c { let mut n = 0; inc{ &n, _ } } else { inc{ n = &m, _ } }\n}',
             'the value of this branch holds `n`, which ends with the branch', 4, 38),
            ('fn inc { mut n: i32 } { n = n + 1 }\nfn f {} {\n    let mut m = 0\n    let mut h = inc{ n = &m, _ }\n    if true {\n        let mut n = 0\n        h = inc{ &n, _ }\n    }\n}',
             'bound function stored in `h` holds `n`, which does not live as long', 7, 9),
            ('fn inc { mut n: i32 } { n = n + 1 }\nfn f {} {\n    let mut m = 0\n    let mut h: &fn{} = inc{ n = &m, _ }\n    while true {\n        let mut n = 0\n        let k = inc{ &n, _ }\n        h = k\n        break\n    }\n}',
             'bound function stored in `h` holds `n`, which does not live as long', 8, 9),
            ('union U { a{ x: i32 }, b }\nfn f { mut u: U } {\n    match &u {\n        a{ &x } => { x = 3 }\n        b => { u = U::b }\n    }\n}',
             'u overlaps the match scrutinee; access it only through the arm bindings', 5, 16),
        ]:
            self.assertSafetyError(src + '\nfn main {} {}', msg, line, col)

    def test_checks(self):
        for src in [
            'fn g { mut x: i32, y: i32 } {}\nfn f {} {\n    let mut n = 0\n    g{ x = &n, y = n }\n}',
            'struct P { a: i32, b: i32 }\nfn g { mut x: i32, mut y: i32 } {}\nfn f {} {\n    let mut p = P{ a = 1, b = 2 }\n    g{ x = &p.a, y = &p.b }\n}',
            'fn f { p: *i32 } -> *i32 {\n    let q = p\n    return q\n}',
            'fn f { mut n: i32 } -> *mut i32 {\n    return &n\n}',
            'fn f {} -> i32 {\n    let x = 1\n    let p = &x\n    return p.*\n}',
            'fn inc { mut n: i32 } { n = n + 1 }\nfn f {} {\n    let mut n = 0\n    let h = inc{ &n, _ }\n    h{}\n}',
            'fn f { c: bool } -> i32 {\n    let x = 1\n    let p = if c { &x } else { &x }\n    return p.*\n}',
            'fn f {} -> []u8 {\n    return "static"\n}',
        ]:
            run(src + '\nfn main {} {}')


class Enums(Base):
    def test_values_and_layout(self):
        self.assertOutput(ENUM + """
struct Tok { kind: Kind, len: u32 }

fn main { mut io: Io } {
    io::println_u64{ &io, n = @as(u64, Kind::number) }
    io::println_u64{ &io, n = @as(u64, Kind::rbrace) }
    io::println_i64{ &io, n = @as(i64, Sign::minus) }
    io::println_i64{ &io, n = @as(i64, Sign::plus) }
    io::println_u64{ &io, n = @size_of(Kind) }
    io::println_u64{ &io, n = @size_of(Tok) }
    io::println_u64{ &io, n = @size_of(Sign) + @align_of(Sign) }
}
""", '1\n41\n-1\n1\n1\n8\n2\n')

    def test_equality(self):
        self.assertOutput(ENUM + """
fn main { mut io: Io } {
    let k = Kind::lbrace
    io::print_bool{ &io, n = k == Kind::lbrace }
    io::print_bool{ &io, n = k != Kind::lbrace }
    io::println_bool{ &io, n = Kind::ident == Kind::number }
}
""", 'truefalsefalse\n')

    def test_match(self):
        self.assertOutput(ENUM + """
fn name { k: Kind } -> utf8::String {
    return match k {
        ident => { "ident" }
        lbrace | rbrace => { "brace" }
        else => { "other" }
    }
}

fn main { mut io: Io } {
    io::println{ &io, s = name{ k = Kind::rbrace } }
    io::println{ &io, s = name{ k = Kind::number } }
    let s = Sign::minus
    match s {
        minus => { io::println{ &io, s = "minus" } }
        zero | plus => { io::println{ &io, s = "not minus" } }
    }
}
""", 'brace\nother\nminus\n')

    def test_from_integer(self):
        self.assertOutput(ENUM + """
fn main { mut io: Io } {
    let n: u32 = 41
    let k = @as(Kind, n)
    io::print_bool{ &io, n = k == Kind::rbrace }
    io::println_bool{ &io, n = @as(Sign, -1) == Sign::minus }
}
""", 'truetrue\n')
        self.assertPanic(ENUM + 'fn main {} { let n = 2\n let k = @as(Kind, n) }',
                         '@as: no variant of Kind has this value')
        self.assertPanic(ENUM + 'fn main {} { let n: u16 = 300\n let k = @as(Kind, n) }',
                         '@as: no variant of Kind has this value')
        self.assertPanic(ENUM + 'fn main {} { let n = @as(u8, Sign::minus) }',
                         '@as: -1 is not representable in u8')

    def test_consts(self):
        self.assertOutput(ENUM + """
const FIRST: Kind = Kind::lbrace
const ORDER: [3]Kind = [Kind::rbrace, Kind::ident, Kind::number]
const BASE: u8 = 200
enum Big: u8 { a = BASE + 1, b, c = 2 * 3 }

fn main { mut io: Io } {
    io::println_u64{ &io, n = @as(u64, ORDER[0]) + @as(u64, FIRST) }
    io::println_u64{ &io, n = @as(u64, Big::b) + @as(u64, Big::c) }
}
""", '81\n208\n')

    def test_errors(self):
        for src, fragment in [
            ('enum E: f64 { a }', 'enum `E` needs an integer base type, got f64'),
            ('enum E: u8 { a, a }', 'duplicate variant `a`'),
            ('enum E: u8 { a = 1, b = 0, c }', '`c` has the same value (1) as `a`'),
            ('enum E: u8 { a = 255, b }', 'value 256 of `b` does not fit in u8'),
            ('enum E(T): u8 { a }', 'an enum cannot have generic parameters'),
            ('enum E: u8 { a = x }', 'an enum value must be a compile-time integer constant'),
            (ENUM + 'fn f {} { let x = Kind::ident < Kind::number }', '`<` needs numbers, got Kind'),
            (ENUM + 'fn f {} { let x = Kind::ident + Kind::number }', '`+` needs numbers, got Kind'),
            (ENUM + 'fn f {} { let k: Kind = 3 }', 'expected Kind, got {integer}'),
            (ENUM + 'fn f {} { let n: u8 = Kind::ident }', 'expected u8, got Kind'),
            (ENUM + 'fn f {} { let x = Kind::ident == 0 }', 'cannot compare Kind with {integer}'),
            (ENUM + 'fn f {} { let x = Kind::ident == Sign::zero }', 'cannot compare Kind with Sign'),
            (ENUM + 'fn f { k: Kind } { match k { ident => {} number => {} } }',
             "match isn't exhaustive: missing lbrace, rbrace"),
            (ENUM + 'fn f { k: Kind } { match k { ident{ x } => {} else => {} } }',
             'variant `ident` has no payload'),
            (ENUM + 'fn f { k: *Kind } { match k { ident => {} else => {} } }',
             'match cannot go through a pointer to an enum'),
            (ENUM + 'fn f {} { let k = Kind::ident{} }', '`Kind::ident` is an enum value; write it without braces'),
            (ENUM + 'fn f {} { let k = @as(Kind, 1.5) }', '@as to an enum takes an integer'),
            (ENUM + 'fn f {} { let x = @as(f64, Kind::ident) }', '@as converts an enum to an integer type'),
            (ENUM + 'fn f {} { let mut k: Kind\n let j = k }', '`k` may be read before it is assigned'),
            (ENUM + 'fn f { k: Kind } { let ident = k else { return } }',
             'a `let` pattern needs a union or optional value, got Kind'),
        ]:
            self.assertCompileError(src + '\nfn main {} {}', fragment)


class ConstData(Base):
    """Consts of array, struct and union type are IR items that each use refers to."""

    def test_tables(self):
        self.assertOutput("""
struct Point { x: i32, y: i32 }
const ORIGIN: Point = Point{ x = 1, y = 2 }
const POINTS: [3]Point = [ORIGIN, Point{ x = 3, y = 4 }, ORIGIN]
const NAMES: [2]utf8::String = ["zero", "one"]
const MAYBE: ?Point = ORIGIN
const LIMIT: i32 = 10

fn main { mut io: Io } {
    let mut i: usize = 0
    let mut sum = 0
    while i < POINTS.len {
        sum = sum + POINTS[i].x * LIMIT + POINTS[i].y
        i = i + 1
    }
    io::println_i64{ &io, n = sum }
    io::println{ &io, s = NAMES[1] }
    let some{ value = p } = MAYBE else { return }
    io::println_i64{ &io, n = p.y }
}
""", '58\none\n2\n')


class CallLookup(Base):
    """In a call or literal, a local that doesn't hold a function doesn't hide a function or type
    of the same name (spec §10, Name lookup, rule 6)."""

    def test_local_named_like_function(self):
        self.assertOutput("""
fn binders {} -> i32 { return 7 }
fn twice { n: i32 } -> i32 { return n * 2 }
fn main { mut io: Io } {
    let binders = binders{}
    let twice = 3
    io::println_i64{ &io, n = binders + twice{ n = twice } }
}
""", '13\n')

    def test_context_field_and_binding(self):
        self.assertOutput("""
struct span { a: i32 }
union U { one{ name: i32 } }
fn name { x: i32 } -> i32 { return x + 1 }
fn show { mut io: Io, name: i32 } {
    match U::one{ name = 40 } {
        one{ name = n } => { io::println_i64{ &io, n = name{ x = n } + name } }
    }
    let span = span{ a = name }
    io::println_i64{ &io, n = span.a }
}
fn main { mut io: Io } { show{ &io, name = 1 } }
""", '42\n1\n')

    def test_function_local_still_shadows(self):
        self.assertOutput("""
fn f {} -> i32 { return 1 }
fn g {} -> i32 { return 2 }
fn main { mut io: Io } {
    let f = g
    io::println_i64{ &io, n = f{} }
}
""", '2\n')

    def test_nothing_else_to_call(self):
        self.assertCompileError("""
fn main {} {
    let n = 1
    _ = n{}
}
""", '`n` has type {integer} and cannot be called')


class GenericApplication(Base):
    def test_space_before_type_arguments(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let e = slice::empty (u8) {}
    let s: ?list::List (i32, arena::Arena) = null
    io::println_bool{ &io, n = e.len == 0 and s == null }
}
""", 'true\n')

    def test_space_in_declaration(self):
        self.assertOutput("""
struct Pair (T) { a: T, b: T }
fn sum (T) { p: Pair (T), f: fn{ x: T, y: T } -> T } -> T { return f{ x = p.a, y = p.b } }
fn add { x: i32, y: i32 } -> i32 { return x + y }
fn main { mut io: Io } { io::println_i64{ &io, n = sum (i32) { p = Pair{ a = 2, b = 3 }, f = add } } }
""", '5\n')

    def test_type_arguments_must_be_on_the_same_line(self):
        with self.assertRaises(CompileError):
            run("""
fn main { mut io: Io } {
    let e = slice::empty
    (u8){}
}
""")


class UnusedResults(Base):
    def test_dropped_result_is_an_error(self):
        self.assertCompileError("""
fn two {} -> i32 { return 2 }
fn main { mut io: Io } { two{} }
""", 'the result of `two` (i32) is unused: use it, or discard it with `_ = ...`')

    def test_dropped_builtin_result_is_an_error(self):
        self.assertCompileError("""
fn main { mut io: Io } { let x: u8 = 1; @wrap_add(x, x) }
""", 'the result of `@wrap_add` (u8) is unused')

    def test_dropped_in_statement_branch(self):
        self.assertCompileError("""
fn two {} -> i32 { return 2 }
fn main { mut io: Io } { if true { two{} } }
""", 'the result of `two` (i32) is unused')

    def test_discard(self):
        self.assertOutput("""
fn say { mut io: Io, n: i64 } -> i64 { io::println_i64{ &io, n }; return n }
fn main { mut io: Io } {
    _ = say{ &io, n = 1 }
    defer _ = say{ &io, n = 3 }
    let x = if true { _ = say{ &io, n = 2 }; 5 } else { 6 }
    _ = x + 1
}
""", '1\n2\n3\n')

    def test_discard_needs_a_value(self):
        self.assertCompileError("""
fn nothing {} { }
fn main { mut io: Io } { _ = nothing{} }
""", 'nothing to discard: this returns no value')

    def test_discard_is_not_a_branch_value(self):
        self.assertCompileError("""
fn two {} -> i32 { return 2 }
fn main { mut io: Io } { let x = if true { _ = two{} } else { 1 } }
""", 'this branch must end in a value')

    def test_underscore_is_not_a_name(self):
        self.assertCompileError("""
fn main { mut io: Io } { let _ = 1 }
""", '`_` is not a name')


class Conditions(Base):
    def test_condition_forms(self):
        self.assertOutput("""
fn even { n: i32 } -> bool { return n % 2 == 0 }
fn main { mut io: Io } {
    let done = true
    if done { io::println_i64{ &io, n = 1 } }
    if even{ n = 4 } { io::println_i64{ &io, n = 2 } }
    if not even{ n = 3 } and even{ n = 2 } { io::println_i64{ &io, n = 3 } }
    if even{ n = 1 } { } else if even{ n = 6 } { io::println_i64{ &io, n = 4 } }
    let mut i = 0
    while i < 3 and not even{ n = 7 } { i = i + 1 }
    io::println_i64{ &io, n = i }
    let v = if even{ n = 2 } { 10 } else { 20 }
    io::println_i64{ &io, n = v }
    if (done) { io::println_i64{ &io, n = 6 } }
    if even{ n = 2 } and
       even{ n = 4 } {
        io::println_i64{ &io, n = 7 }
    }
}
""", '1\n2\n3\n4\n3\n10\n6\n7\n')

    def test_match_on_call(self):
        self.assertOutput("""
fn pick { n: i32 } -> ?i32 { if n > 0 { return n } else { return null } }
fn main { mut io: Io } {
    match pick{ n = 5 } {
        some{ value } => { io::println_i64{ &io, n = value } }
        null          => { }
    }
    let k = match pick{ n = -1 } { some{ value } => { value } null => { 0 } }
    io::println_i64{ &io, n = k }
}
""", '5\n0\n')

    def test_if_expression_in_call_in_condition(self):
        self.assertOutput("""
fn even { n: i32 } -> bool { return n % 2 == 0 }
fn main { mut io: Io } {
    let a = 3
    if even{ n = if a > 2 { 4 } else { 5 } } { io::println_i64{ &io, n = 1 } }
}
""", '1\n')

    def test_postfix_on_parenthesized_if_and_match(self):
        # §11, If and match expressions, rule 9.
        self.assertOutput("""
struct P { x: i32 }
fn main { mut io: Io } {
    let a = P{ x = 1 }
    let b = P{ x = 2 }
    io::println_i64{ &io, n = (if a.x > 1 { a } else { b }).x }
    let o: ?P = a
    io::println_i64{ &io, n = (match o { some{ value } => { value } null => { b } }).x }
}
""", '2\n1\n')


class Builtins(Base):
    def test_unknown_builtin(self):
        self.assertCompileError('fn main { mut io: Io } { let x = @nope(1) }', 'unknown builtin `@nope`')

    def test_wrong_argument_count(self):
        self.assertCompileError('fn main { mut io: Io } { let x = @as(i32) }',
                                'wrong number of arguments: @as(T, x)')
        self.assertCompileError('fn main { mut io: Io } { let x = @size_of(i32, 1) }',
                                'wrong number of arguments: @size_of(T)')
        self.assertCompileError('fn main { mut io: Io } { @panic("a", "b") }',
                                'wrong number of arguments: @panic() or @panic("reason")')
        self.assertCompileError('fn main { mut io: Io } { let x = @wrap_add(1) }',
                                'wrong number of arguments: @wrap_add(a, b)')

    def test_parentheses_required(self):
        self.assertCompileError('fn main { mut io: Io } { @panic }', "expected '(' after @panic")

    def test_type_argument_parsed_as_type(self):
        # `S` names both a struct and a local; in a type position it can only be the struct.
        self.assertOutput("""
struct S { a: u8, b: u32 }
fn main { mut io: Io } {
    let S: u8 = 1
    io::println_u64{ &io, n = @size_of(S) + @align_of(*S) + @as(u64, S) }
}
""", '17\n')

    def test_value_argument_parsed_as_expression(self):
        self.assertCompileError('fn main { mut io: Io } { let x = @addr(i32) }', '`i32` is a type, not a value')

    def test_type_argument_from_the_type_expected(self):
        # `_` is the type expected: a local's, an assignment's, a field's, a return type, the
        # other operand's, and an optional's payload.
        self.assertOutput("""
#c::symbol{ name = "llabs" }
extern fn long_abs { n: i64 } -> i64
type Abs = extern fn{ n: i64 } -> i64
struct Fns { abs: Abs }

fn small { n: i32 } -> i32 { return n }
fn back { p: *u8 } -> ?Abs { return @cast(_, p) }

fn main { mut io: Io } -> i32 {
    let f: Abs = long_abs
    let p: *u8 = @cast(_, f)
    let mut g: Abs = long_abs
    g = @cast(_, p)
    let fns = Fns{ abs = @cast(_, p) }
    let big: i64 = 300
    let a: i32 = @as(_, big)
    let o: ?i16 = @as(_, big)
    let t: u8 = @trunc(_, big)
    let some{ value = h } = back{ p } else { return 1 }
    let some{ value = s } = o else { return 1 }
    io::println_i64{ &io, n = g{ n = -4 } + fns.abs{ n = -2 } + h{ n = -1 } }
    io::println_i64{ &io, n = small{ n = @as(_, big) } + a + 1 }
    io::println_i64{ &io, n = @as(i64, t) + s }
    return 0
}
""", '7\n601\n344\n')

    def test_type_argument_from_the_type_expected_errors(self):
        no_type = 'takes the type expected here, and nothing here expects one: write the type'
        elsewhere = '`_` is a type only as the type argument of @as, @trunc or @cast, where it is the type expected'
        for src, msg in [
            ('fn main {} { let big: i64 = 3\n    let x = @as(_, big) }', '@as(_, ...) ' + no_type),
            ('fn main {} { let big: i64 = 3\n    if @trunc(_, big) == 3 {} }', '@trunc(_, ...) ' + no_type),
            ('fn main {} { let x: u8 = 3\n    let p = @cast(_, &x) }', '@cast(_, ...) ' + no_type),
            # a generic parameter not yet inferred isn't a type expected
            ('fn id(T) { x: T } -> T { return x }\nfn main {} { let big: i64 = 3\n    _ = id{ x = @as(_, big) } }', '@as(_, ...) ' + no_type),
            ('fn main {} { let x: u8 = 3\n    let s: []u8 = @cast(_, &x) }', '@cast needs a pointer or extern fn target type, got []u8'),
            ('fn main {} { let x: _ = 1 }', elsewhere),
            ('fn main {} { let n = @size_of(_) }', elsewhere),
            ('fn f { x: ?_ } {}\nfn main {} {}', elsewhere),
        ]:
            self.assertCompileError(src, msg)


class LoopControl(Base):
    def test_break_and_continue(self):
        self.assertOutput("""
fn first_even { a: [5]i32 } -> ?usize {
    let mut i: usize = 0
    let mut found: ?usize = null
    while i < a.len {
        if a[i] % 2 == 0 { found = i; break }
        i = i + 1
    }
    return found
}
fn main { mut io: Io } {
    let r = first_even{ a = [1, 3, 8, 5, 6] }
    if r != null { io::println_u64{ &io, n = r } }
    let mut sum = 0
    let mut i = 0
    while i < 10 {
        i = i + 1
        if i % 2 == 1 { continue }
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
    while i < 3 {
        let mut j = 0
        while true {
            j = j + 1
            if j == 4 { break }
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
    while i < cmds.len {
        match cmds[i] {
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
    while true {
        n = n + 1
        if n < 10 { continue }
        return n
    }
}
fn main { mut io: Io } { io::println_i64{ &io, n = spin{} } }
""", '10\n')

    def test_loop_with_break_needs_return(self):
        self.assertCompileError("""
fn f {} -> i32 { while true { break } }
fn main { mut io: Io } { }
""", 'must end every path')

    def test_assign_once_then_break(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let x: i32
    while true { x = 7; break }
    io::println_i64{ &io, n = x }
}
""", '7\n')

    def test_assign_in_repeating_loop(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let x: i32
    let mut i = 0
    while i < 3 { x = i; i = i + 1 }
}
""", 'assigned in a loop that can repeat')

    def test_assign_before_continue(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let x: i32
    while true { x = 1; continue }
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
    if o != null { io::println_i64{ &io, n = o } }
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

    def test_wider_result_panics_at_wider_range(self):
        self.assertPanic("""
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
                                'expected *i64, got *mut i32')
        self.assertCompileError('fn main { mut io: Io } { let a: ?i32 = 1; let b: ?i64 = a }',
                                'expected ?i64, got ?i32')

    def test_mut_field_needs_exact_type(self):
        self.assertCompileError("""
fn bump { mut n: i64 } { n = n + 1 }
fn main { mut io: Io } { let mut a: i32 = 1; bump{ n = &a } }
""", 'expected *mut i64, got *mut i32')


def run_io(src, stdin=b''):
    out, err = io.StringIO(), io.StringIO()
    run_source(src, out=out, err=err, inp=io.BytesIO(stdin))
    return out.getvalue(), err.getvalue()


class ReadOnlyPointers(Base):
    def test_addr_of_mutable_place_writes(self):
        self.assertOutput("""
struct P { x: i32 }
fn set { p: *mut P, v: i32 } { p.x = v }
fn main { mut io: Io } {
    let mut a = P{ x = 1 }
    set{ p = &a, v = 5 }
    let q = &a.x
    q.* = q.* + 1
    io::println_i64{ &io, n = a.x }
}
""", '6\n')

    def test_addr_of_read_only_place_is_read_only(self):
        self.assertCompileError("""
fn main { mut io: Io } { let a: i32 = 1; let p = &a; p.* = 2 }
""", 'cannot write through *i32')
        self.assertCompileError("""
fn set { p: *mut i32 } { p.* = 1 }
fn main { mut io: Io } { let a: i32 = 1; set{ p = &a } }
""", 'expected *mut i32, got *i32')

    def test_no_writes_through_read_only_pointer(self):
        self.assertCompileError("""
struct P { x: i32 }
fn f { p: *P } { p.x = 1 }
fn main { mut io: Io } { }
""", 'cannot write through *P')
        self.assertCompileError("""
fn f { p: *[4]i32 } { p[0] = 1 }
fn main { mut io: Io } { }
""", 'cannot write through *[4]i32')
        self.assertCompileError("""
fn f { p: *i32 } { (p + 1).* = 1 }
fn main { mut io: Io } { }
""", 'cannot write through *i32')

    def test_read_only_pointer_cannot_fill_mut_field(self):
        self.assertCompileError("""
fn bump { mut n: i32 } { n = n + 1 }
fn f { p: *i32 } { bump{ n = p } }
fn main { mut io: Io } { }
""", 'expected *mut i32, got *i32')

    def test_mut_converts_to_read_only(self):
        self.assertOutput("""
fn get { p: *i32 } -> i32 { return p.* }
fn first { p: ?*i32 } -> i32 {
    let some{ value } = p else { return 0 }
    return value.*
}
fn main { mut io: Io } {
    let mut a: i32 = 7
    let p: *mut i32 = &a
    let q: *i32 = p
    let o: ?*mut i32 = p
    io::println_i64{ &io, n = get{ p } + first{ p = o } + q.* }
    io::println_bool{ &io, n = p == q }
}
""", '21\ntrue\n')

    def test_read_only_does_not_convert_to_mut(self):
        self.assertCompileError("""
fn main { mut io: Io } { let a: i32 = 1; let p: *mut i32 = &a }
""", 'expected *mut i32, got *i32')
        self.assertCompileError("""
fn main { mut io: Io } { let mut a: i32 = 1; let p: ?*i32 = &a; let q: ?*mut i32 = p }
""", 'expected ?*mut i32, got ?*i32')

    def test_generic_pointer_inference(self):
        self.assertOutput("""
fn get(T) { p: *T } -> T { return p.* }
fn main { mut io: Io } {
    let mut a: i32 = 4
    io::println_i64{ &io, n = get{ p = &a } }
}
""", '4\n')

    def test_match_through_read_only_pointer(self):
        self.assertOutput(SHAPE + """
fn size { s: *Shape } -> i32 {
    match s {
        circle{ &r } => { return r }
        else         => { return 0 }
    }
}
fn main { mut io: Io } {
    let s = Shape::circle{ r = 3 }
    io::println_i64{ &io, n = size{ s = &s } }
}
""", '3\n')
        self.assertCompileError(SHAPE + """
fn grow { s: *Shape } {
    match s { circle{ &r } => { r = r + 1 } else => { } }
}
fn main { mut io: Io } { }
""", 'cannot assign to `r`: it is bound through a read-only pointer')
        self.assertCompileError(SHAPE + """
fn main { mut io: Io } {
    let s = Shape::circle{ r = 3 }
    match &s { circle{ &r } => { r = 4 } else => { } }
}
""", 'bound through a read-only pointer')

    def test_mut_pointer_type_text(self):
        self.assertCompileError("""
fn main { mut io: Io } { let mut a: i32 = 1; let p: **mut i32 = &a }
""", 'expected **mut i32, got *mut i32')


class Slices(Base):
    def test_index_len_and_ptr(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let mut a = [10, 20, 30]
    let s: []mut i32 = &a
    s[1] = s[1] + 1
    io::println_i64{ &io, n = a[1] }
    io::println_u64{ &io, n = s.len }
    io::println_i64{ &io, n = s.ptr[2] }
}
""", '21\n3\n30\n')

    def test_sub_slices(self):
        self.assertOutput("""
fn show { mut io: Io, xs: []i32 } {
    let mut i: usize = 0
    while i < xs.len { io::print_i64{ &io, n = xs[i] }; i = i + 1 }
    io::newline{ &io }
}
fn main { mut io: Io } {
    let a = [1, 2, 3, 4, 5]
    show{ &io, xs = a[1..3] }
    show{ &io, xs = a[..2] }
    show{ &io, xs = a[3..] }
    show{ &io, xs = a[..] }
    let p = &a
    show{ &io, xs = p[2..4][1..] }
}
""", '23\n12\n45\n12345\n4\n')

    def test_bounds(self):
        self.assertPanic("""
fn main { mut io: Io } { let a = [1, 2]; let s = a[..]; let i: usize = 2; let x = s[i] }
""", 'index 2 out of bounds for length 2')
        self.assertPanic("""
fn main { mut io: Io } { let a = [1, 2]; let s = a[..]; let n: usize = 3; let t = s[1..n] }
""", 'range 1..3 out of bounds for length 2')
        self.assertPanic("""
fn main { mut io: Io } { let a = [1, 2]; let s = a[..]; let lo: usize = 2; let t = s[lo..1] }
""", 'range 2..1 out of bounds for length 2')

    def test_zero_value_is_empty(self):
        self.assertOutput("""
struct Buf { data: []u8, n: i32 }
fn main { mut io: Io } {
    let mut s: []u8
    let mut b: Buf
    io::println_u64{ &io, n = s.len + b.data.len + s[0..0].len }
}
""", '0\n')

    def test_read_only_slices(self):
        self.assertCompileError("""
fn f { xs: []i32 } { xs[0] = 1 }
fn main { mut io: Io } { }
""", 'cannot write through []i32; it needs to be a `[]mut`')
        self.assertCompileError("""
fn f { xs: []i32 } { xs.ptr[0] = 1 }
fn main { mut io: Io } { }
""", 'cannot write through *i32')
        self.assertCompileError("""
fn f { xs: []mut i32 } { }
fn main { mut io: Io } { let a: [2]i32 = [1, 2]; f{ xs = &a } }
""", 'expected []mut i32, got *[2]i32')
        self.assertCompileError("""
fn main { mut io: Io } { let a: [2]i32 = [1, 2]; let s: []mut i32 = a[..] }
""", 'expected []mut i32, got []i32')

    def test_mut_converts_to_read_only(self):
        self.assertOutput("""
fn first { xs: []i32 } -> i32 { return xs[0] }
fn opt { xs: ?[]i32 } -> usize {
    let some{ value } = xs else { return 0 }
    return value.len
}
fn main { mut io: Io } {
    let mut a = [7, 8]
    let m: []mut i32 = &a
    let o: ?[]mut i32 = m
    io::println_i64{ &io, n = first{ xs = m } }
    io::println_u64{ &io, n = opt{ xs = o } }
}
""", '7\n2\n')

    def test_slice_builtin(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let mut a = [1, 2, 3]
    let s = @slice(&a[1], 2)
    s[1] = 9
    io::println_i64{ &io, n = a[2] }
}
""", '9\n')
        self.assertCompileError("""
fn main { mut io: Io } { let s = @slice(3, 2) }
""", '@slice needs a pointer, got {integer}')

    def test_generic_inference_from_array(self):
        self.assertOutput("""
fn count(T) { xs: []T } -> usize { return xs.len }
fn main { mut io: Io } {
    let a = [1.5, 2.5]
    io::println_u64{ &io, n = count{ xs = &a } }
}
""", '2\n')

    def test_len_and_ptr_are_not_places(self):
        self.assertCompileError("""
fn main { mut io: Io } { let mut s: []u8; s.len = 3 }
""", '`.len` is not a place')

    def test_escape(self):
        self.assertCompileError("""
fn f {} -> []u8 { let mut a: [4]u8; return a[..] }
fn main { mut io: Io } { }
""", 'returned value holds the address of local `a`')
        self.assertCompileError("""
fn f {} -> []u8 { let mut a: [4]u8; let s: []u8 = &a; return s[1..] }
fn main { mut io: Io } { }
""", 'returned value holds the address of local `a`')

    def test_cannot_slice(self):
        self.assertCompileError("""
fn main { mut io: Io } { let x = 3; let s = x[..] }
""", 'cannot slice {integer}')

    def test_cast_keeps_read_only(self):
        self.assertCompileError("""
fn f { p: *u8 } { let q = @cast(*mut i8, p) }
fn main { mut io: Io } { }
""", '@cast cannot make *u8 writable')

    def test_type_text(self):
        self.assertCompileError("""
fn main { mut io: Io } { let mut a: [1]i32 = [1]; let s: [][]mut u8 = &a }
""", 'expected [][]mut u8, got *mut [1]i32')


class LiteralViews(Base):
    """A string literal where a []u8 or a utf8::String is expected views static bytes."""

    def test_views(self):
        self.assertOutput(r"""
struct Named { name: utf8::String }
fn greet {} -> utf8::String {
    return "from a function"
}
fn show { mut io: Io, b: []u8 } {
    io::println_u64{ &io, n = b.len }
}
fn main { mut io: Io } {
    io::println{ &io, s = "hello" }
    io::println{ &io, s = greet{} }
    show{ &io, b = "abc" }
    show{ &io, b = "\xff" }
    show{ &io, b = "" }
    let o: ?[]u8 = "xy"
    if o != null { io::println_u64{ &io, n = o.len } }
    let n = Named{ name = "caf\xc3\xa9" }
    io::println{ &io, s = n.name }
    let arr = "four"
    io::println_u64{ &io, n = arr.len + @size_of([4]u8) }
}
""", 'hello\nfrom a function\n3\n1\n0\n2\ncafé\n8\n')

    def test_branches_follow_a_view(self):
        self.assertOutput("""
union Kind { a, b, c }
fn name { k: Kind, other: utf8::String } -> utf8::String {
    let s = match k {
        a => { "first" }
        b => { other }
        c => { "third" }
    }
    return s
}
fn main { mut io: Io } {
    io::println{ &io, s = name{ k = Kind::a, other = "x" } }
    io::println{ &io, s = name{ k = Kind::b, other = "second" } }
    let n = if true { "yes" } else { name{ k = Kind::c, other = "x" } }
    io::println{ &io, s = n }
}
""", 'first\nsecond\nyes\n')

    def test_same_literal_twice(self):
        self.assertOutput("""
fn view {} -> []u8 { return "same" }
fn main { mut io: Io } {
    io::println_bool{ &io, n = view{}.ptr == view{}.ptr }
}
""", 'true\n')

    def test_const_tables(self):
        self.assertOutput("""
namespace kw {
    const WORDS: [3][]u8 = ["fn", "let", "match"]
    const NAMES: [2]utf8::String = ["zero", "one"]
    const COPY: [3][]u8 = WORDS
    struct Entry { name: utf8::String, arity: i32 }
    const ENTRIES: [2]Entry = [Entry{ name = "add", arity = 2 }, Entry{ name = "neg", arity = 1 }]
}
fn name { i: usize } -> utf8::String { return kw::NAMES[i] }
fn main { mut io: Io } {
    let mut i: usize = 0
    while i < kw::WORDS.len { io::println_u64{ &io, n = kw::WORDS[i].len }; i = i + 1 }
    io::println{ &io, s = name{ i = 1 } }
    io::println_u64{ &io, n = kw::COPY[0].len }
    io::println{ &io, s = kw::ENTRIES[1].name }
    io::println_i64{ &io, n = kw::ENTRIES[0].arity }
}
""", '2\n3\n5\none\n2\nneg\n2\n')

    def test_mut_slice_rejected(self):
        self.assertCompileError('fn f { b: []mut u8 } { }\nfn main { mut io: Io } { f{ b = "abc" } }',
                                'a string literal is read-only')

    def test_invalid_utf8_rejected(self):
        self.assertCompileError(r'fn main { mut io: Io } { io::println{ &io, s = "ok\xc3" } }',
                                'string literal is not valid UTF-8 (byte 2)')

    def test_view_is_read_only(self):
        self.assertCompileError('fn main { mut io: Io } {\n    let b: []u8 = "abc"\n    b[0] = 1\n}',
                                'cannot write through []u8')


FMT_SETUP = """
fn main { mut io: Io } {
    let mut mem: [4096]u8
    let mut heap = arena::new{ buf = mem[..] }
    let mut b = utf8::builder{ realloc = arena::alloc, &heap }
%s
    io::println{ &io, s = utf8::view{ b } }
}
"""


class Fmt(Base):
    def fmt(self, body, expected, extra=''):
        self.assertOutput(extra + FMT_SETUP % body, expected + '\n')

    def fmt_error(self, body, fragment, extra=''):
        self.assertCompileError(extra + FMT_SETUP % body, fragment)

    def test_holes(self):
        self.fmt(r"""
    let name = utf8::of{ chars = "caf\xc3\xa9" }
    let small: u8 = 7
    _ = @fmt(&b, "{} {} {} {} {} {}|{c}|{{}}|{}", -3, small, 1.5, true, name, @as(f32, 0.5), 'A', "lit")""",
                 '-3 7 1.5 true caf\u00e9 0.5|A|{}|lit')

    def test_widths_and_hex(self):
        self.fmt(r"""
    let name = utf8::of{ chars = "ab" }
    _ = @fmt(&b, "[{5}][{05}][{05}][{x}][{08x}][{4}][{1}]", 42, 42, -42, 255, 48879, name, name)""",
                 '[   42][00042][-0042][ff][0000beef][  ab][ab]')

    def test_writer_function(self):
        self.fmt("""
    let d = Date{ y = 2026, m = 9, d = 30 }
    _ = @fmt(&b, "due {}, or {}", write_iso{ d, _ }, write_us{ d, sep = '/', _ })""",
                 'due 2026-09-30, or 09/30/2026', extra="""
struct Date { y: u32, m: u32, d: u32 }
fn write_iso { mut b: utf8::Builder(arena::Arena), d: Date } -> bool {
    return @fmt(&b, "{04}-{02}-{02}", d.y, d.m, d.d)
}
fn write_us { mut out: utf8::Builder(arena::Arena), d: Date, sep: u8 } -> bool {
    return @fmt(&out, "{02}{c}{02}{c}{}", d.m, sep, d.d, sep, d.y)
}
""")

    def test_open_integer_types(self):
        # The pushes are chosen once the body is checked, so `n` is still free to become a usize.
        self.fmt("""
    let mut n = 0
    _ = @fmt(&b, "{}", n)
    let xs: [2]usize = [1, 2]
    while n < xs.len { n = n + 1 }
    _ = @fmt(&b, " {}", n)""", '0 2')

    def test_field_builder_and_result(self):
        self.fmt("""
    let mut w = W{ out = utf8::builder{ realloc = arena::alloc, &heap } }
    let ok = @fmt(&w.out, "{}+{}", 1, 2)
    _ = @fmt(&b, "{}", ok)
    _ = utf8::push{ &b, s = utf8::view{ b = w.out } }""", 'true1+2', extra='struct W { out: utf8::Builder(arena::Arena) }\n')

    def test_out_of_memory(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let mut mem: [8]u8
    let mut heap = arena::new{ buf = mem[..] }
    let mut b = utf8::builder{ realloc = arena::alloc, &heap }
    io::println_bool{ &io, n = @fmt(&b, "{}", 1234) }
    io::println_bool{ &io, n = @fmt(&b, "{} and more than eight bytes", 5) }
}
""", 'true\nfalse\n')

    def test_errors(self):
        for body, fragment in [
            ('_ = @fmt(&b, "{} {}", 1)', 'the format has 2 holes but 1 argument follows it'),
            ('_ = @fmt(&b, "x", 1, 2)', 'the format has 0 holes but 2 arguments follow it'),
            ('let f = "{}"\n    _ = @fmt(&b, f, 1)', '@fmt takes its format as a string literal'),
            ('_ = @fmt(&b, "{", 1)', 'the format has a `{` without a `}`'),
            ('_ = @fmt(&b, "}")', 'the format has a `}` without a `{`'),
            ('_ = @fmt(&b, "{y}", 1)', 'bad hole `{y}` in the format'),
            ('let n: i32 = 1\n    _ = @fmt(&b, "{x}", n)', '`{x}` formats an unsigned integer, not i32'),
            ('_ = @fmt(&b, "{4c}", 65)', '`{4c}`: a width applies to numbers and text'),
            ('_ = @fmt(&b, "{4}", 1.5)', '`{4}`: a width applies to integers and utf8::String, not f64'),
            ('_ = @fmt(&b, "{}", [1, 2])', "@fmt can't format [2]i32"),
            ('let s: []u8 = "x"\n    _ = @fmt(&b, "{}", s)', "@fmt can't format []u8"),
            ('let mut n: i32 = 1\n    _ = @fmt(&n, "x")','@fmt writes to a *mut utf8::Builder, got *mut i32'),
            ('let bs: [1]utf8::Builder(arena::Arena) = [b]\n    _ = @fmt(&bs[0], "x")',
             '@fmt takes its builder as `&b`, `&x.f` or a name'),
            ('@fmt(&b, "x")', 'the result of `@fmt` (bool) is unused'),
        ]:
            self.fmt_error(body, fragment)


    def test_program_utf8_does_not_hide_std(self):
        # @fmt pushes with std's utf8, even where a namespace of the program's is called utf8.
        self.assertOutput("""
namespace app {
    namespace utf8 {
        fn push { x: i32 } -> bool { return false }
    }
    fn show { mut io: Io } {
        let mut mem: [64]u8
        let mut heap = arena::new{ buf = mem[..] }
        let mut b = std_utf8{ &heap }
        if @fmt(&b, "{} and {}", 42, true) { io::println{ &io, s = view{ b } } }
    }
}
fn std_utf8 { mut heap: arena::Arena } -> utf8::Builder(arena::Arena) {
    return utf8::builder{ realloc = arena::alloc, &heap }
}
fn view { b: utf8::Builder(arena::Arena) } -> utf8::String { return utf8::view{ b } }
fn main { mut io: Io } { app::show{ &io } }
""", '42 and true\n')

class StdLib(Base):
    def test_hello(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let hi = "hello, \\"world\\"\\t!"
    io::println{ &io, s = utf8::of{ chars = &hi } }
    io::put_char{ &io, c = 'x' }
    io::newline{ &io }
}
""", 'hello, "world"\t!\nx\n')

    def test_stderr(self):
        out, err = run_io("""
fn main { mut io: Io } {
    let a = "out"
    let b = "err"
    io::println{ &io, s = utf8::of{ chars = &a } }
    io::eprintln{ &io, s = utf8::of{ chars = &b } }
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
    match r {
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
    show{ &io, r = utf8::parse_i64{ s = utf8::of{ chars = &a } } }
    show{ &io, r = utf8::parse_i64{ s = utf8::of{ chars = &b } } }
    show{ &io, r = utf8::parse_i64{ s = utf8::of{ chars = &c } } }
    show{ &io, r = utf8::parse_i64{ s = utf8::of{ chars = &d } } }
    show{ &io, r = utf8::parse_i64{ s = utf8::of{ chars = &e } } }
    let u = "18446744073709551616"
    io::println_bool{ &io, n = utf8::parse_u64{ s = utf8::of{ chars = &u } } == null }
}
""", '-9223372036854775808\n0\n0\n0\n42\ntrue\n')

    def test_string_ops(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let raw = "  Hello, World \\n"
    let s = utf8::trim{ s = utf8::of{ chars = &raw } }
    io::println{ &io, s }
    io::println_u64{ &io, n = utf8::len{ s } }
    let hel = "Hello"
    let rld = "rld"
    io::println_bool{ &io, n = utf8::starts_with{ s, prefix = utf8::of{ chars = &hel } } }
    io::println_bool{ &io, n = utf8::ends_with{ s, suffix = utf8::of{ chars = &rld } } }
    io::println_bool{ &io, n = utf8::eq{ a = s, b = utf8::of{ chars = &hel } } }
    let comma = utf8::find{ s, c = ',' }
    if comma != null {
        io::println{ &io, s = utf8::sub{ s, lo = 0, hi = comma } }
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
    let mut heap = arena::new{ buf = mem[..] }
    let mut b = utf8::builder{ realloc = arena::alloc, &heap }
    let name = "count"
    _ = utf8::push{ &b, s = utf8::of{ chars = &name } }
    _ = utf8::push_char{ &b, c = '=' }
    _ = utf8::push_i64{ &b, n = -1234567 }
    _ = utf8::push_char{ &b, c = ' ' }
    _ = utf8::push_u64{ &b, n = 99 }
    io::println{ &io, s = utf8::view{ b } }
    utf8::free{ &b}
    io::println_u64{ &io, n = utf8::len{ s = utf8::view{ b } } }
}
""", 'count=-1234567 99\n0\n')

    def test_read_line(self):
        out, _ = run_io("""
fn main { mut io: Io } {
    let mut buf: [8]u8
    let mut total: i64 = 0
    let mut more = true
    while more {
        let line = io::read_line{ &io, into = buf[..] }
        if line == null {
            more = false
        } else {
            let n = utf8::parse_i64{ s = utf8::trim{ s = line } }
            if n != null { total = total + n }
            io::println{ &io, s = line }
        }
    }
    io::println_i64{ &io, n = total }
}
""", b'12\r\n30\nabcdefghij\n  -2\nlast')
        self.assertEqual(out, '12\n30\nabcdefgh\nij\n  -2\nlast\n40\n')

    def test_read_line_replaces_invalid_utf8(self):
        out, _ = run_io("""
fn main { mut io: Io } {
    let mut buf: [8]u8
    while true {
        let line = io::read_line{ &io, into = buf[..] }
        if line == null { break }
        io::println{ &io, s = line }
    }
}
""", b'caf\xc3\xa9\nx\xffy\nabcdefg\xc3\xa9\n')
        # The last line's é is cut in two by the 8-byte buffer, so each half becomes '?'.
        self.assertEqual(out, 'café\nx?y\nabcdefg?\n?\n')

    def test_parse_float(self):
        self.assertOutput("""
fn show { mut io: Io, r: ?f64 } {
    match r {
        null => { io::println_bool{ &io, n = false } }
        some{ value } => { io::println_f64{ &io, n = value } }
    }
}
fn show32 { mut io: Io, r: ?f32 } {
    match r {
        null => { io::println_bool{ &io, n = false } }
        some{ value } => { io::println_f32{ &io, n = value } }
    }
}
fn main { mut io: Io } {
    let a = "-0.25"
    let b = "6.02E23"
    let c = "1e+100"
    let d = "3"
    let e = "-inf"
    let f = "1e999"
    let g = "1."
    let h = ".5"
    let i = "1e"
    let j = "+1"
    show{ &io, r = utf8::parse_f64{ s = utf8::of{ chars = &a } } }
    show{ &io, r = utf8::parse_f64{ s = utf8::of{ chars = &b } } }
    show{ &io, r = utf8::parse_f64{ s = utf8::of{ chars = &c } } }
    show{ &io, r = utf8::parse_f64{ s = utf8::of{ chars = &d } } }
    show{ &io, r = utf8::parse_f64{ s = utf8::of{ chars = &e } } }
    show{ &io, r = utf8::parse_f64{ s = utf8::of{ chars = &f } } }
    show{ &io, r = utf8::parse_f64{ s = utf8::of{ chars = &g } } }
    show{ &io, r = utf8::parse_f64{ s = utf8::of{ chars = &h } } }
    show{ &io, r = utf8::parse_f64{ s = utf8::of{ chars = &i } } }
    show{ &io, r = utf8::parse_f64{ s = utf8::of{ chars = &j } } }
    let k = "1.1"
    let l = "1e39"
    let m = "1.000000059604644775390625000001"
    show32{ &io, r = utf8::parse_f32{ s = utf8::of{ chars = &k } } }
    show32{ &io, r = utf8::parse_f32{ s = utf8::of{ chars = &l } } }
    show32{ &io, r = utf8::parse_f32{ s = utf8::of{ chars = &m } } }
}
""", '-0.25\n6.02e+23\n1e+100\n3.0\n-inf\nfalse\nfalse\nfalse\nfalse\nfalse\n'
     '1.1\nfalse\n1.0000001\n')

    def test_parse_float_round_trips(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let xs = [0.1, -2.5e-300, 1.7976931348623157e308, 5e-324, 123456.789]
    let mut buf: [32]u8
    let mut i: usize = 0
    while i < xs.len {
        let text = utf8::fmt_f64{ n = xs[i], into = buf[..] }
        let back = utf8::parse_f64{ s = text }
        if back != null { io::println_bool{ &io, n = back == xs[i] } }
        i = i + 1
    }
}
""", 'true\n' * 5)

    def test_cursor(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let src = "  let x1 = 42 -> y"
    let mut cur = utf8::cursor{ s = utf8::of{ chars = &src } }
    utf8::skip_space{ &cur }
    io::println{ &io, s = utf8::take_while{ &cur, f = utf8::is_alpha } }
    utf8::skip_space{ &cur }
    io::println{ &io, s = utf8::take_while{ &cur, f = utf8::is_alnum } }
    utf8::skip_space{ &cur }
    io::println_bool{ &io, n = utf8::eat{ &cur, ch = '+' } }
    io::println_bool{ &io, n = utf8::eat{ &cur, ch = '=' } }
    utf8::skip_space{ &cur }
    let n = utf8::parse_i64{ s = utf8::take_while{ &cur, f = utf8::is_digit } }
    if n != null { io::println_i64{ &io, n } }
    utf8::skip_space{ &cur }
    let c = utf8::peek_at{ cur, ahead = 1 }
    if c != null { io::put_char{ &io, c } }
    let arrow = "->"
    io::println_bool{ &io, n = utf8::eat_str{ &cur, s = utf8::of{ chars = &arrow } } }
    io::println{ &io, s = utf8::rest{ cur } }
    _ = utf8::bump{ &cur }
    let y = utf8::bump{ &cur }
    if y != null { io::put_char{ &io, c = y } }
    io::println_bool{ &io, n = utf8::done{ cur } }
    io::println_bool{ &io, n = utf8::bump{ &cur } == null and utf8::peek{ cur } == null }
}
""", 'let\nx1\nfalse\ntrue\n42\n>true\n y\nytrue\ntrue\n')

    def test_split_and_search(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let kv = "key=val=ue"
    let s = utf8::of{ chars = &kv }
    let sp = utf8::split_once{ s, c = '=' }
    if sp != null {
        io::println{ &io, s = sp.head }
        io::println{ &io, s = sp.tail }
    }
    io::println_bool{ &io, n = utf8::split_once{ s, c = ';' } == null }
    let val = "val"
    let at = utf8::find_str{ s, needle = utf8::of{ chars = &val } }
    if at != null { io::println_u64{ &io, n = at } }
    let long = "key=val=ue!"
    io::println_bool{ &io, n = utf8::find_str{ s, needle = utf8::of{ chars = &long } } == null }
    let padded = "  x  "
    let p = utf8::of{ chars = &padded }
    io::println_u64{ &io, n = utf8::len{ s = utf8::trim_start{ s = p } } }
    io::println_u64{ &io, n = utf8::len{ s = utf8::trim_end{ s = p } } }
}
""", 'key\nval=ue\ntrue\n4\ntrue\n3\n3\n')

    def test_slice_helpers(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let mut a: [5]i32
    let s = a[..]
    slice::fill{ s, v = 3 }
    s[4] = 9
    io::println_i64{ &io, n = a[0] + a[4] }
    io::println_u64{ &io, n = s.len }
    io::println_u64{ &io, n = s[2..2].len + s[3..].len + s[..4].len }
}
""", '12\n5\n6\n')

    def test_non_ascii_literal_rejected(self):
        self.assertCompileError('fn main { mut io: Io } { let b = "café" }', 'non-ASCII')

    def test_slice_bounds_panic(self):
        self.assertPanic("""
fn main { mut io: Io } {
    let mut a: [2]u8
    let s = a[..]
    let x = s[2]
}
""", 'index 2 out of bounds for length 2')

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
fn greet {} -> utf8::String {
    let hi = "hi"
    return utf8::of{ chars = &hi }
}
fn main { mut io: Io } { }
""", 'returned value holds the address of local `hi`')

    def test_panic_in_std_reports_std_file(self):
        with self.assertRaises(Panic) as cm:
            run_source("""
fn main { mut io: Io } {
    let mut a: [2]u8
    let b: [4]u8 = [1, 2, 3, 4]
    slice::copy{ dst = a[..], src = b[..] }
}
""", 'user.ctx', out=io.StringIO())
        self.assertEqual(cm.exception.pos[2], 'std/slice.ctx')

    def test_error_reports_user_file(self):
        with self.assertRaises(CompileError) as cm:
            run_source('fn main { mut io: Io } { io::println_i64{ &io, n = "x" } }', 'user.ctx')
        self.assertEqual(cm.exception.pos[2], 'user.ctx')
        self.assertIn('expected i64, got [1]u8', cm.exception.msg)


MAP_SETUP = """
fn main { mut io: Io } {
    let mut mem: [262144]u8
    let mut heap = arena::new{ buf = mem[..] }
    let mut m = map::new(i32, i64){ realloc = arena::alloc, &heap, hash = map::hash_i32, eq = map::eq_i32 }
%s
}
"""


class Map(Base):
    def run_map(self, body, expected):
        self.assertOutput(MAP_SETUP % body, expected)

    def test_put_get_grow(self):
        self.run_map("""
    let mut i = 0
    while i < 1000 {
        _ = map::put{ &m, key = i * 7, value = i }
        i = i + 1
    }
    io::println_u64{ &io, n = map::len{ m } }
    let mut sum: i64 = 0
    i = 0
    while i < 1000 {
        let v = map::get{ m, key = i * 7 }
        if v != null { sum = sum + v }
        i = i + 1
    }
    io::println_i64{ &io, n = sum }
    io::println_bool{ &io, n = map::has{ m, key = 8 } }
""", '1000\n499500\nfalse\n')

    def test_replace_and_at(self):
        self.run_map("""
    _ = map::put{ &m, key = -5, value = 1 }
    _ = map::put{ &m, key = -5, value = 2 }
    io::println_u64{ &io, n = map::len{ m } }
    let p = map::at{ m, key = -5 }
    if p != null { p.* = p.* + 40 }
    let v = map::get{ m, key = -5 }
    if v != null { io::println_i64{ &io, n = v } }
    io::println_bool{ &io, n = map::at{ m, key = 6 } == null }
""", '1\n42\ntrue\n')

    def test_remove(self):
        self.run_map("""
    let mut i = 0
    while i < 50 {
        _ = map::put{ &m, key = i, value = i }
        i = i + 1
    }
    i = 0
    while i < 50 {
        if i % 2 == 0 { _ = map::remove{ &m, key = i } }
        i = i + 1
    }
    io::println_u64{ &io, n = map::len{ m } }
    io::println_bool{ &io, n = map::remove{ &m, key = 4 } == null }
    let r = map::remove{ &m, key = 7 }
    if r != null { io::println_i64{ &io, n = r } }
    io::println_bool{ &io, n = map::has{ m, key = 9 } and not map::has{ m, key = 10 } }
    // Churn: removed slots are reused or dropped, so the table doesn't fill with them.
    i = 0
    while i < 2000 {
        _ = map::put{ &m, key = 100, value = i }
        _ = map::remove{ &m, key = 100 }
        i = i + 1
    }
    io::println_u64{ &io, n = map::len{ m } }
    io::println_bool{ &io, n = m.slots.len <= 128 }
""", '25\ntrue\n7\ntrue\n24\ntrue\n')

    def test_iterate_and_each(self):
        self.assertOutput("""
fn add { mut total: i64, key: i32, value: i64 } { total = total + value }
""" + MAP_SETUP % """
    let mut i = 1
    while i <= 10 {
        _ = map::put{ &m, key = i, value = i * 100 }
        i = i + 1
    }
    let mut keys: i32 = 0
    let mut cursor: usize = 0
    while true {
        match map::next{ m, &cursor } {
            null => { break }
            some{ value } => {
                keys = keys + value.key
                if value.key % 2 == 0 { _ = map::remove{ &m, key = value.key } }
            }
        }
    }
    io::println_i64{ &io, n = keys }
    io::println_u64{ &io, n = map::len{ m } }
    let mut total: i64 = 0
    map::each{ m, f = add{ &total, _ } }
    io::println_i64{ &io, n = total }
""", '55\n5\n2500\n')

    def test_string_keys(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let mut mem: [8192]u8
    let mut heap = arena::new{ buf = mem[..] }
    let mut counts = map::new(utf8::String, i32){
        realloc = arena::alloc, &heap, hash = map::hash_string, eq = utf8::eq,
    }
    let text = "the cat and the dog and the bird"
    let mut cur = utf8::cursor{ s = utf8::of{ chars = &text } }
    while not utf8::done{ cur } {
        let word = utf8::take_while{ &cur, f = utf8::is_alpha }
        let p = map::at{ m = counts, key = word }
        if p != null {
            p.* = p.* + 1
        } else {
            _ = map::put{ m = &counts, key = word, value = 1 }
        }
        utf8::skip_space{ &cur }
    }
    io::println_u64{ &io, n = map::len{ m = counts } }
    let the = "the"
    let n = map::get{ m = counts, key = utf8::of{ chars = &the } }
    if n != null { io::println_i64{ &io, n } }
}
""", '5\n3\n')

    def test_clear_and_free(self):
        self.run_map("""
    _ = map::put{ &m, key = 1, value = 1 }
    _ = map::put{ &m, key = 2, value = 2 }
    map::clear{ &m }
    io::println_u64{ &io, n = map::len{ m } }
    io::println_bool{ &io, n = map::has{ m, key = 1 } }
    _ = map::put{ &m, key = 3, value = 3 }
    io::println_u64{ &io, n = map::len{ m } }
    map::free{ &m}
    io::println_u64{ &io, n = m.slots.len }
    io::println_bool{ &io, n = map::get{ m, key = 3 } == null }
""", '0\nfalse\n1\n0\ntrue\n')

    def test_allocation_failure(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let mut mem: [256]u8
    let mut heap = arena::new{ buf = mem[..] }
    let mut m = map::new(u64, u64){ realloc = arena::alloc, &heap, hash = map::hash_u64, eq = map::eq_u64 }
    let mut i: u64 = 0
    let mut ok = true
    while ok {
        ok = map::put{ &m, key = i, value = i }
        if ok { i = i + 1 }
    }
    io::println_u64{ &io, n = i }
    io::println_u64{ &io, n = map::len{ m } }
    io::println_bool{ &io, n = map::has{ m, key = i - 1 } and not map::has{ m, key = i } }
}
""", '6\n6\ntrue\n')

    def test_key_needs_matching_hash(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let mut mem: [64]u8
    let mut heap = arena::new{ buf = mem[..] }
    let m = map::new(i32, i32){ realloc = arena::alloc, &heap, hash = map::hash_i64, eq = map::eq_i32 }
}
""", 'expected')


class Utf8(Base):
    # "café €=😀!": 1 + 1 + 1 + 2 + 1 + 3 + 1 + 4 + 1 bytes
    TEXT = r'let lit = "caf\xc3\xa9 \xe2\x82\xac=\xf0\x9f\x98\x80!"' + '\n    let s = utf8::of{ chars = &lit }\n'

    def test_basics(self):
        out, err = run_io(r"""
fn main { mut io: Io } {
    %s
    io::println{ &io, s }
    io::println_u64{ &io, n = utf8::len{ s } }
    io::println_u64{ &io, n = utf8::count{ s } }
    io::println_u64{ &io, n = utf8::at{ s, i = 3 } }
    io::println_bool{ &io, n = utf8::is_boundary{ s, i = 4 } }
    io::println_bool{ &io, n = utf8::is_boundary{ s, i = 5 } }
    io::println_bool{ &io, n = utf8::is_boundary{ s, i = 15 } }
    io::println{ &io, s = utf8::sub{ s, lo = 6, hi = 9 } }
    let euro = "\xe2\x82\xac"
    opt{ &io, n = utf8::find_str{ s, needle = utf8::of{ chars = &euro } } }
    opt{ &io, n = utf8::find{ s, c = 128512 } }
    opt{ &io, n = utf8::find{ s, c = 234 } }
    let caf = "caf"
    io::println_bool{ &io, n = utf8::starts_with{ s, prefix = utf8::of{ chars = &caf } } }
    let bang = "\xf0\x9f\x98\x80!"
    io::println_bool{ &io, n = utf8::ends_with{ s, suffix = utf8::of{ chars = &bang } } }
    let sp = utf8::split_once{ s, c = 8364 }
    if sp != null {
        io::println{ &io, s = sp.head }
        io::println{ &io, s = sp.tail }
    }
    let hi = "  hi\t"
    io::println{ &io, s = utf8::trim{ s = utf8::of{ chars = &hi } } }
    io::eprintln{ &io, s = utf8::sub{ s, lo = 0, hi = 5 } }
}
fn opt { mut io: Io, n: ?usize } {
    match n {
        null          => { io::println_i64{ &io, n = -1 } }
        some{ value } => { io::println_u64{ &io, n = value } }
    }
}
""".replace('%s', self.TEXT))
        self.assertEqual(out, 'café €=😀!\n15\n9\n233\nfalse\ntrue\ntrue\n€\n6\n10\n-1\n'
                              'true\ntrue\ncafé \n=😀!\nhi\n')
        self.assertEqual(err, 'café\n')

    def test_validation(self):
        cases = [
            (r'\x80', 0), (r'a\xc0\xaf', 1), (r'\xe0\x80\xaf', 0), (r'\xed\xa0\x80', 0),
            (r'\xf4\x90\x80\x80', 0), (r'ab\xe2\x82', 2), (r'\xf5\x80\x80\x80', 0), (r'\xc3\x28', 0),
            (r'\xc2\x80', None), (r'\xed\x9f\xbf', None), (r'\xee\x80\x80', None),
            (r'\xf0\x90\x80\x80', None), (r'\xf4\x8f\xbf\xbf', None), ('', None),
        ]
        body = ''.join('    let b%d = "%s"\n    check{ &io, bytes = b%d[..] }\n' % (i, lit, i)
                       for i, (lit, _) in enumerate(cases))
        src = """
fn check { mut io: Io, bytes: []u8 } {
    match utf8::from{ bytes } {
        ok                  => { io::println_i64{ &io, n = -1 } }
        utf8::invalid{ at } => { io::println_u64{ &io, n = at } }
    }
}
fn main { mut io: Io } {
%s}
""" % body
        self.assertOutput(src, ''.join('%d\n' % (-1 if at is None else at) for _, at in cases))

    def test_encode_round_trip(self):
        points = [0, 127, 128, 2047, 2048, 55295, 57344, 65535, 65536, 1114111]
        body = ''.join("""    let e%d = utf8::encode{ c = %d, into = buf[..] }
    io::println_u64{ &io, n = utf8::len{ s = e%d } }
    io::println_bool{ &io, n = utf8::at{ s = e%d, i = 0 } == %d }
""" % (i, c, i, i, c) for i, c in enumerate(points))
        expected = ''.join('%d\ntrue\n' % len(chr(c).encode('utf-8')) for c in points)
        self.assertOutput('fn main { mut io: Io } {\n    let mut buf: [4]u8\n%s}\n' % body, expected)

    def test_panics(self):
        self.assertPanic(r"""
fn main { mut io: Io } {
    %s
    let t = utf8::sub{ s, lo = 0, hi = 4 }
}
""".replace('%s', self.TEXT), 'utf8::sub: offset is inside a character')
        self.assertPanic('fn main { mut io: Io } {\n    %s    let c = utf8::at{ s, i = 4 }\n}\n' % self.TEXT,
                        'utf8: offset is not the start of a character')
        self.assertPanic("""
fn main { mut io: Io } {
    let mut buf: [4]u8
    let e = utf8::encode{ c = 55296, into = buf[..] }
}
""", 'utf8::encode: not a Unicode scalar value')
        self.assertPanic(r"""
fn main { mut io: Io } {
    let bad = "\xff"
    let s = utf8::of{ chars = &bad }
}
""", "utf8::of: the bytes aren't valid UTF-8")

    def test_cursor(self):
        self.assertOutput(r"""
fn main { mut io: Io } {
    let lit = "  \xc3\xa9t\xc3\xa9=42 \xe2\x82\xac"
    let mut cur = utf8::cursor{ s = utf8::of{ chars = &lit } }
    utf8::skip_space{ &cur }
    opt{ &io, n = utf8::peek{ cur } }
    opt{ &io, n = utf8::peek_at{ cur, ahead = 1 } }
    io::println{ &io, s = utf8::take_while{ &cur, f = not_eq } }
    io::println_bool{ &io, n = utf8::eat{ &cur, ch = '=' } }
    io::println{ &io, s = utf8::take_while{ &cur, f = utf8::is_digit } }
    utf8::skip_space{ &cur }
    io::println_bool{ &io, n = utf8::eat{ &cur, ch = 8364 } }
    io::println_bool{ &io, n = utf8::done{ cur } }
    io::println_bool{ &io, n = utf8::bump{ &cur } == null }
    io::println_bool{ &io, n = utf8::peek_at{ cur, ahead = 0 } == null }
}
fn not_eq { c: u32 } -> bool { return c != '=' }
fn opt { mut io: Io, n: ?u32 } {
    match n {
        null          => { io::println_i64{ &io, n = -1 } }
        some{ value } => { io::println_u64{ &io, n = value } }
    }
}
""", '233\n116\nété\ntrue\n42\ntrue\ntrue\ntrue\ntrue\n')

    def test_builder(self):
        self.assertOutput(r"""
fn main { mut io: Io } {
    let mut mem: [1024]u8
    let mut heap = arena::new{ buf = mem[..] }
    let mut b = utf8::builder{ realloc = arena::alloc, &heap }
    let name = "caf"
    _ = utf8::push{ &b, s = utf8::of{ chars = &name } }
    _ = utf8::push_char{ &b, c = 233 }
    _ = utf8::push_char{ &b, c = '=' }
    _ = utf8::push_i64{ &b, n = -7 }
    _ = utf8::push_char{ &b, c = 128512 }
    io::println{ &io, s = utf8::view{ b } }
    io::println_u64{ &io, n = utf8::count{ s = utf8::view{ b } } }
    utf8::free{ &b}
}
""", 'café=-7😀\n8\n')


SHAPE = """
union Shape { circle{ r: i32 }, square{ side: i32 }, rect{ w: i32, h: i32 }, dot, line }
"""


class SharedArms(Base):
    def test_without_bindings(self):
        self.assertOutput(SHAPE + """
fn round { s: Shape } -> bool {
    return match s {
        circle | dot => { true }
        else         => { false }
    }
}
fn main { mut io: Io } {
    io::println_bool{ &io, n = round{ s = Shape::dot } }
    io::println_bool{ &io, n = round{ s = Shape::circle{ r = 1 } } }
    io::println_bool{ &io, n = round{ s = Shape::line } }
    let o: ?i32 = 3
    match o { null | some => { io::println_i64{ &io, n = 1 } } }
}
""", 'true\ntrue\nfalse\n1\n')

    def test_shared_bindings(self):
        self.assertOutput(SHAPE + """
fn size { s: Shape } -> i32 {
    return match s {
        circle{ r = n } | square{ side = n } => { n }
        rect{ w, h }                         => { w * h }
        dot
        | line                               => { 0 }
    }
}
fn main { mut io: Io } {
    io::println_i64{ &io, n = size{ s = Shape::circle{ r = 7 } } }
    io::println_i64{ &io, n = size{ s = Shape::square{ side = 4 } } }
    io::println_i64{ &io, n = size{ s = Shape::rect{ w = 2, h = 3 } } }
    io::println_i64{ &io, n = size{ s = Shape::line } }
}
""", '7\n4\n6\n0\n')

    def test_shared_bindings_through_pointer(self):
        self.assertOutput(SHAPE + """
fn grow { s: *mut Shape } {
    match s {
        circle{ &r = n } | square{ &side = n } => { n = n + 1 }
        else                                   => { }
    }
}
fn main { mut io: Io } {
    let mut s = Shape::square{ side = 4 }
    grow{ s = &s }
    let square{ side } = s else { @panic() }
    io::println_i64{ &io, n = side }
}
""", '5\n')

    def test_missing_binding(self):
        self.assertCompileError(SHAPE + """
fn f { s: Shape } -> i32 {
    match s { circle{ r } | square => { return r } else => { return 0 } }
}
fn main { mut io: Io } { }
""", '`square` must bind `r`, as `circle` in the same arm does')

    def test_extra_binding(self):
        self.assertCompileError(SHAPE + """
fn f { s: Shape } -> i32 {
    match s { circle{ r } | rect{ w = r, h } => { return r } else => { return 0 } }
}
fn main { mut io: Io } { }
""", '`rect` binds `h`, which `circle` in the same arm does not')

    def test_binding_types_differ(self):
        self.assertCompileError("""
union U { a{ x: i32 }, b{ x: u8 } }
fn f { u: U } { match u { a{ x } | b{ x } => { } } }
fn main { mut io: Io } { }
""", '`x` is i32 in `a` but u8 in `b`')

    def test_binding_modes_differ(self):
        self.assertCompileError(SHAPE + """
fn f { s: *Shape } { match s { circle{ &r } | square{ side = r } => { } else => { } } }
fn main { mut io: Io } { }
""", '`r` must be bound with `&` in both `circle` and `square`, or in neither')

    def test_variant_repeated_in_arm(self):
        self.assertCompileError(SHAPE + """
fn f { s: Shape } { match s { dot | dot => { } else => { } } }
fn main { mut io: Io } { }
""", 'variant `dot` appears in more than one arm')

    def test_else_cannot_be_shared(self):
        self.assertCompileError(SHAPE + """
fn f { s: Shape } { match s { dot | else => { } } }
fn main { mut io: Io } { }
""", "expected a name, found 'else'")


class Expressions(Base):
    def test_if_expression(self):
        self.assertOutput("""
fn sign { n: i64 } -> i64 {
    return if n < 0 { -1 } else if n == 0 { 0 } else { 1 }
}
fn main { mut io: Io } {
    io::println_i64{ &io, n = sign{ n = -5 } + sign{ n = 0 } * 10 + sign{ n = 9 } * 100 }
    let n = 4
    let v = if n > 3 {
        let doubled = n * 2
        doubled + 1
    } else {
        0
    }
    io::println_i64{ &io, n = v }
    io::println_i64{ &io, n = if n == 4 { 10 } else { 20 } + 1 }
}
""", '99\n9\n11\n')

    def test_match_expression(self):
        self.assertOutput("""
union Shape { circle{ r: i64 }, square{ side: i64 }, point }
fn area { s: Shape } -> i64 {
    return match s {
        circle{ r }    => { 3 * r * r }
        square{ side } => { side * side }
        point          => { 0 }
    }
}
fn main { mut io: Io } {
    io::println_i64{ &io, n = area{ s = Shape::circle{ r = 2 } } }
    io::println_i64{ &io, n = area{ s = Shape::square{ side = 5 } } }
    let o: ?i32 = 7
    let x = match o { null => { 0 } some{ value } => { value } }
    io::println_i64{ &io, n = x }
}
""", '12\n25\n7\n')

    def test_expected_type_and_join(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let small: u8 = 3
    let w = if true { small } else { 100 }      // the literal becomes u8
    let wide: i64 = if false { small } else { -1 }
    let o: ?i32 = if false { 5 } else { null }
    let p = if true { 5 } else { null }           // joins to ?i32
    let f: f64 = if true { 1.5 } else { 2.0 }
    io::println_u64{ &io, n = w }
    io::println_i64{ &io, n = wide }
    io::println_bool{ &io, n = o == null }
    io::println_bool{ &io, n = p != null }
    io::println_f64{ &io, n = f }
}
""", '3\n-1\ntrue\ntrue\n1.5\n')

    def test_narrowing_in_if_expression(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let o = utf8::parse_i64{ s = utf8::empty{} }
    let x = if o != null { o } else { 42 }
    let y = if o == null { 1 } else { o }
    io::println_i64{ &io, n = x + y }
}
""", '43\n')

    def test_branches_can_leave(self):
        self.assertOutput("""
fn first_even { xs: [5]i64 } -> i64 {
    let mut i: usize = 0
    let mut found: i64 = -1
    while i < xs.len {
        let x = if xs[i] % 2 == 0 { xs[i] } else { i = i + 1; continue }
        found = x
        break
    }
    return found
}
fn pick { o: ?i64 } -> i64 {
    let v = match o { null => { return -1 } some{ value } => { value } }
    return v * 10
}
fn main { mut io: Io } {
    io::println_i64{ &io, n = first_even{ xs = [1, 3, 8, 5, 6] } }
    io::println_i64{ &io, n = pick{ o = 4 } }
    io::println_i64{ &io, n = pick{ o = null } }
    let n = match utf8::parse_i64{ s = utf8::empty{} } {
        null => { 0 }
        some{ value } => { value }
    }
    io::println_i64{ &io, n }
}
""", '8\n40\n-1\n0\n')

    def test_nested_branches(self):
        self.assertOutput("""
fn f { c: bool } -> i32 {
    let x = if c { if c { return 1 } else { return 2 } } else { 3 }
    return x
}
fn main { mut io: Io } {
    io::println_i64{ &io, n = f{ c = true } }
    io::println_i64{ &io, n = f{ c = false } }
    let o: ?i32 = 4
    let y = if true {
        match o {
            null => { 0 }
            some{ value } => { if value > 3 { 30 } else { 3 } }
        }
    } else {
        1
    }
    io::println_i64{ &io, n = y }
}
""", '1\n3\n30\n')

    def test_panic_branch(self):
        self.assertPanic("""
fn main { mut io: Io } {
    let o: ?i32 = null
    let x = match o { null => { @panic() } some{ value } => { value } }
}
""", '@panic()')

    def test_if_statement_unchanged(self):
        self.assertOutput("""
fn main { mut io: Io } {
    if true { io::println_i64{ &io, n = 1 } }
    match utf8::parse_i64{ s = utf8::empty{} } {
        null => { io::println_i64{ &io, n = 2 } }
        else => { }
    }
}
""", '1\n2\n')

    def test_needs_else(self):
        self.assertCompileError('fn main { mut io: Io } { let x = if true { 1 } }',
                                'needs an `else`')

    def test_branch_types_differ(self):
        self.assertCompileError('fn main { mut io: Io } { let x = if true { 1 } else { true } }',
                                'branches have different types')

    def test_branch_without_value(self):
        self.assertCompileError('fn main { mut io: Io } { let x = if true { let a = 1 } else { 1 } }',
                                'must end in a value')

    def test_void_branch(self):
        self.assertCompileError(
            'fn main { mut io: Io } { let x = if true { io::newline{ &io } } else { 1 } }',
            'has no value')

    def test_no_branch_produces_value(self):
        self.assertCompileError("""
fn f {} -> i32 {
    let x = if true { return 1 } else { return 2 }
    return x
}
fn main { mut io: Io } { }
""", 'no branch of this expression produces a value')

    def test_branch_escape(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let p = if true { let y = 1; &y } else { let z = 2; &z }
}
""", 'holds the address of local `y`')

    def test_branch_bound_escape(self):
        self.assertCompileError("""
fn g { mut a: i32, b: i32 } { }
fn main { mut io: Io } {
    let h = if true { let mut y = 0; g{ a = &y, _ } } else { let mut z = 0; g{ a = &z, _ } }
}
""", 'holds `y`')

    def test_branch_address_of_outer_local(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let a = 1
    let b = 2
    let p = if true { &a } else { &b }
    io::println_i64{ &io, n = p.* }
}
""", '1\n')

    def test_escape_through_expression(self):
        self.assertCompileError("""
fn f {} -> *i32 {
    let a = 1
    return if true { &a } else { &a }
}
fn main { mut io: Io } { }
""", 'returned value holds the address of local `a`')


class ResultType(Base):
    """std's Result(T, E) gave way to `!T` (spec §8, Errors): its test of passing errors up."""

    def test_propagation(self):
        self.assertOutput("""
error empty
error bad{ at: usize }
fn parse_one { s: utf8::String } -> !i64 {
    if utf8::len{ s } == 0 { return empty }
    let mut i: usize = 0
    while i < utf8::len{ s } {
        if not utf8::is_digit{ c = utf8::at{ s, i } } { return bad{ at = i } }
        i = i + 1
    }
    return utf8::parse_i64{ s } ifnull { return bad{ at = 0 } }
}
fn sum { s: utf8::String } -> !i64 {
    let parts = utf8::split_once{ s, c = ',' } ifnull { return empty }
    let x = try parse_one{ s = parts.head }
    let y = try parse_one{ s = parts.tail }
    return x + y
}
fn report { mut io: Io, r: !i64 } {
    let code = match r {
        ok{ value }  => { value }
        err{ error } => { match error { empty => { -1 } bad{ at } => { -100 - @as(i64, at) } else => { -2 } } }
    }
    io::println_i64{ &io, n = code }
}
fn main { mut io: Io } {
    let a = "12,30"
    let b = "12,3x"
    let c = "12"
    report{ &io, r = sum{ s = utf8::of{ chars = &a } } }
    report{ &io, r = sum{ s = utf8::of{ chars = &b } } }
    report{ &io, r = sum{ s = utf8::of{ chars = &c } } }
}
""", '42\n-101\n-1\n')

    def test_result_is_a_free_name(self):
        self.assertOutput("""
struct Result { n: i32 }
fn main { mut io: Io } { io::println_i64{ &io, n = Result{ n = 3 }.n } }
""", '3\n')

class NarrowingAfterIf(Base):
    """§8 Optional: an `if` whose null branch leaves narrows x for the rest of the block."""

    def test_then_leaves(self):
        self.assertOutput("""
fn f { x: ?i32 } -> i32 {
    if x == null { return -1 }
    return x + 1
}
fn main { mut io: Io } {
    io::println_i64{ &io, n = f{ x = 4 } }
    io::println_i64{ &io, n = f{ x = null } }
}
""", '5\n-1\n')

    def test_else_leaves(self):
        self.assertOutput("""
fn f { x: ?i32 } -> i32 {
    let y = x
    if y != null { } else { return -1 }
    return y * 2
}
fn main { mut io: Io } {
    io::println_i64{ &io, n = f{ x = 4 } }
    io::println_i64{ &io, n = f{ x = null } }
}
""", '8\n-1\n')

    def test_in_loop_with_continue(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let xs: [3]?i32 = [1, null, 3]
    let mut i: usize = 0
    while i < xs.len {
        let x = xs[i]
        i = i + 1
        if x == null { continue }
        io::println_i64{ &io, n = x }
    }
}
""", '1\n3\n')

    def test_ends_with_the_block(self):
        self.assertCompileError("""
fn f { x: ?i32 } -> i32 {
    if true {
        if x == null { return 0 }
    }
    return x
}
fn main {} { }
""", 'expected i32, got ?i32')

    def test_not_when_branch_may_finish(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let x: ?i32 = 1
    if x == null { io::println_i64{ &io, n = 0 } }
    let y = x + 1
}
""", 'incompatible types')

    def test_not_when_else_is_missing(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let x: ?i32 = 1
    if x != null { return }
    let y = x + 1
}
""", 'incompatible types')

    def test_mutable_not_narrowed(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let mut x: ?i32 = 1
    if x == null { return }
    let y = x + 1
}
""", 'incompatible types')

    def test_outer_variable_can_be_shadowed(self):
        self.assertOutput("""
fn f { x: ?i32 } -> i32 {
    if x == null { return 0 }
    let x = x * 10
    return x
}
fn main { mut io: Io } { io::println_i64{ &io, n = f{ x = 7 } } }
""", '70\n')

    def test_same_scope_cannot_be_redeclared(self):
        self.assertCompileError("""
fn main {} {
    let x: ?i32 = 1
    if x == null { return }
    let x = 2
}
""", 'already declared')


class NarrowingConditions(Base):
    """§8 Optional: narrowing through `and`, `or` and `not`, of field paths, and in `while`."""

    def test_and_or_not(self):
        self.assertOutput("""
fn both { a: ?i32, b: ?i32 } -> i32 {
    if a != null and b != null { return a + b }
    return 0
}
fn big { a: ?i32 } -> bool { return a == null or a > 3 }
fn inv { a: ?i32 } -> i32 {
    if not (a == null) { return a }
    return -1
}
fn after { a: ?i32, b: ?i32 } -> i32 {
    if a == null or b == null { return 0 }
    return a * b
}
fn main { mut io: Io } {
    io::println_i64{ &io, n = both{ a = 2, b = 3 } }
    io::println_i64{ &io, n = both{ a = 2, b = null } }
    io::println_bool{ &io, n = big{ a = null } }
    io::println_bool{ &io, n = big{ a = 2 } }
    io::println_i64{ &io, n = inv{ a = 7 } }
    io::println_i64{ &io, n = after{ a = 4, b = 5 } }
    io::println_i64{ &io, n = after{ a = null, b = 5 } }
}
""", '5\n0\ntrue\nfalse\n7\n20\n0\n')

    def test_fields(self):
        self.assertOutput("""
struct Inner { tag: ?i32 }
struct Node { kids: ?[]i32, inner: Inner }
fn first { n: Node } -> i32 {
    if n.kids != null and n.kids.len > 0 { return n.kids[0] }
    return -1
}
fn tag { o: ?Node } -> i32 {
    if o == null or o.inner.tag == null { return 0 }
    let p = &o.inner.tag
    return o.inner.tag + p.*
}
fn main { mut io: Io } {
    let ks = [3, 4]
    let n = Node{ kids = ks[..], inner = Inner{ tag = 5 } }
    io::println_i64{ &io, n = first{ n } }
    io::println_i64{ &io, n = first{ n = Node{ kids = null, inner = Inner{ tag = null } } } }
    io::println_i64{ &io, n = tag{ o = n } }
    io::println_i64{ &io, n = tag{ o = null } }
}
""", '3\n-1\n10\n0\n')

    def test_while(self):
        self.assertOutput("""
struct S { limit: ?i32 }
fn count { s: S } -> i32 {
    let mut n = 0
    while s.limit != null and n < s.limit { n = n + 1 }
    return n
}
fn main { mut io: Io } {
    io::println_i64{ &io, n = count{ s = S{ limit = 4 } } }
    io::println_i64{ &io, n = count{ s = S{ limit = null } } }
}
""", '4\n0\n')

    def test_or_does_not_narrow_when_true(self):
        self.assertCompileError("""
fn f { a: ?i32, b: ?i32 } -> i32 {
    if a != null or b != null { return a }
    return 0
}
fn main {} { }
""", 'expected i32, got ?i32')

    def test_and_does_not_narrow_after_when_false_may_finish(self):
        self.assertCompileError("""
fn f { a: ?i32 } -> i32 {
    if a != null and a > 0 { }
    return a
}
fn main {} { }
""", 'expected i32, got ?i32')

    def test_mutable_field_not_narrowed(self):
        self.assertCompileError("""
struct S { a: ?i32 }
fn main { mut io: Io } {
    let mut s = S{ a = 1 }
    if s.a != null { io::println_i64{ &io, n = s.a } }
}
""", 'expected i64, got ?i32')

    def test_field_through_pointer_not_narrowed(self):
        self.assertCompileError("""
struct S { a: ?i32 }
fn f { p: *S } -> i32 {
    if p.a != null { return p.a }
    return 0
}
fn main {} { }
""", 'expected i32, got ?i32')


class LabeledLoops(Base):
    """§11 Statements: `break L` and `continue L` leave or repeat the enclosing loop labeled L."""

    def test_break_and_continue(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let mut i = 0
    outer:
    while i < 4 {
        i = i + 1
        let mut j = 0
        while j < 4 {
            j = j + 1
            if j == 2 { continue outer }
            if i == 3 { break outer }
            io::println_i64{ &io, n = i * 10 + j }
        }
    }
    io::println_i64{ &io, n = i }
}
""", '11\n21\n3\n')

    def test_label_on_the_same_line_and_innermost(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let mut n = 0
    a: while true {
        n = n + 1
        if n == 3 { break a }
    }
    io::println_i64{ &io, n }
}
""", '3\n')

    def test_three_levels_and_defers(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let mut i = 0
    top:
    while i < 3 {
        i = i + 1
        defer { io::println_i64{ &io, n = -i } }
        while true {
            defer { io::println_i64{ &io, n = 100 } }
            while true {
                if i == 2 { break top }
                continue top
            }
        }
    }
}
""", '100\n-1\n100\n-2\n')

    def test_break_out_of_while_true(self):
        self.assertOutput("""
fn find { xs: [3][3]i32, want: i32 } -> i32 {
    let mut found: i32
    let mut r: usize = 0
    rows:
    while true {
        let mut c: usize = 0
        while true {
            if xs[r][c] == want { found = @as(i32, r * 3 + c); break rows }
            c = c + 1
            if c == 3 { break }
        }
        r = r + 1
        if r == 3 { found = -1; break }
    }
    return found
}
fn main { mut io: Io } {
    let xs = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    io::println_i64{ &io, n = find{ xs, want = 6 } }
    io::println_i64{ &io, n = find{ xs, want = 0 } }
}
""", '5\n-1\n')

    def test_from_an_if_expression(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let mut i = 0
    outer:
    while i < 10 {
        i = i + 1
        while true {
            let d = if i < 3 { i * 2 } else { break outer }
            io::println_i64{ &io, n = d }
            break
        }
    }
    io::println_i64{ &io, n = i }
}
""", '2\n4\n3\n')

    def test_sibling_loops_share_a_label(self):
        self.assertOutput("""
fn main { mut io: Io } {
    a: while true { break a }
    a: while true { break a }
    io::println_i64{ &io, n = 1 }
}
""", '1\n')

    def test_unknown_label(self):
        self.assertCompileError('fn main {} { while true { break nope } }',
                                'no enclosing loop is labeled `nope`')

    def test_label_reused_by_nested_loop(self):
        self.assertCompileError("""
fn main {} {
    a: while true {
        a: while true { break a }
    }
}
""", 'loop label `a` is already used by an enclosing loop')

    def test_only_while_is_labeled(self):
        self.assertCompileError('fn main {} {\n    a: if true { }\n}', 'only a `while` can be labeled')

    def test_defer_cannot_leave_through_a_label(self):
        self.assertCompileError("""
fn main {} {
    a: while true {
        defer { while true { break a } }
        break
    }
}
""", 'no enclosing loop is labeled `a` in this defer')


class LetElse(Base):
    """§11 Let-else: `let variant{ ... } = e else { ... }`."""

    SRC = """
union Result(T, E) { ok{ value: T }, err{ error: E } }
union E { odd{ n: i32 }, negative }
fn half { n: i32 } -> Result(i32, E) {
    if n < 0 { return Result::err{ error = E::negative } }
    if n % 2 != 0 { return Result::err{ error = E::odd{ n } } }
    return Result::ok{ value = n / 2 }
}
"""

    def test_result_propagation(self):
        self.assertOutput(self.SRC + """
fn quarter { n: i32 } -> Result(i32, E) {
    let ok{ value = h } = half{ n } else err{ error } { return Result::err{ error } }
    let ok{ value } = half{ n = h } else err{ error } { return Result::err{ error } }
    return Result::ok{ value }
}
fn show { mut io: Io, r: Result(i32, E) } {
    let ok{ value } = r else err{ error } {
        let odd{ n } = error else { io::println_i64{ &io, n = -1000 }; return }
        io::println_i64{ &io, n = -n }
        return
    }
    io::println_i64{ &io, n = value }
}
fn main { mut io: Io } {
    show{ &io, r = quarter{ n = 12 } }
    show{ &io, r = quarter{ n = 6 } }
    show{ &io, r = quarter{ n = -4 } }
}
""", '3\n-3\n-1000\n')

    def test_optional(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let xs: [3]?i32 = [1, null, 3]
    let mut i: usize = 0
    while i < xs.len {
        let x = xs[i]
        i = i + 1
        let some{ value = v } = x else { io::println_i64{ &io, n = 0 }; continue }
        io::println_i64{ &io, n = v }
    }
}
""", '1\n0\n3\n')

    def test_variant_without_bindings(self):
        self.assertOutput("""
union Result(T, E) { ok{ value: T }, err{ error: E } }
fn main { mut io: Io } {
    let x: ?i32 = null
    let null = x else { @panic() }
    let r: Result(i32, bool) = Result::ok{ value = 1 }
    let ok = r else { @panic() }
    io::println_i64{ &io, n = 1 }
}
""", '1\n')

    def test_else_runs_defers(self):
        self.assertOutput("""
fn f { mut io: Io, x: ?i32 } {
    defer io::println_i64{ &io, n = 99 }
    let some{ value } = x else { return }
    io::println_i64{ &io, n = value }
}
fn main { mut io: Io } {
    f{ &io, x = 5 }
    f{ &io, x = null }
}
""", '5\n99\n99\n')

    def test_rename_in_match(self):
        self.assertOutput("""
union P { pt{ x: i32, y: i32 } }
fn main { mut io: Io } {
    let mut p = P::pt{ x = 1, y = 2 }
    match &p { pt{ &x = a, y = b } => { a = a + b } }
    match p { pt{ x = a } => { io::println_i64{ &io, n = a } } }
}
""", '3\n')

    def test_else_must_leave(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let x: ?i32 = 1
    let some{ value } = x else { io::println_i64{ &io, n = 0 } }
}
""", 'must leave')

    def test_bindings_not_visible_in_else(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let x: ?i32 = 1
    let some{ value } = x else { io::println_i64{ &io, n = value }; return }
}
""", 'unknown name `value`')

    def test_else_pattern_must_be_the_only_other_variant(self):
        self.assertCompileError(self.SRC + """
union T { a, b, c }
fn main {} {
    let t = T::a
    let a = t else b { return }
}
""", 'would skip c')

    def test_else_pattern_repeats_variant(self):
        self.assertCompileError("""
fn main {} {
    let x: ?i32 = 1
    let some{ value } = x else some { return }
}
""", 'both sides')

    def test_needs_else(self):
        self.assertCompileError("""
fn main {} {
    let x: ?i32 = 1
    let some{ value } = x
}
""", 'needs an `else`')

    def test_needs_union(self):
        self.assertCompileError("""
fn main {} {
    let x = 1
    let some = x else { return }
}
""", 'needs a union or optional')

    def test_unknown_variant(self):
        self.assertCompileError("""
fn main {} {
    let x: ?i32 = 1
    let ok{ value } = x else { return }
}
""", 'no variant `ok`')

    def test_no_pointer_scrutinee(self):
        self.assertCompileError("""
fn main {} {
    let x: ?i32 = 1
    let p = &x
    let some{ value } = p else { return }
}
""", 'through a pointer')

    def test_no_amp_binding(self):
        self.assertCompileError("""
fn main {} {
    let x: ?i32 = 1
    let some{ &value } = x else { return }
}
""", 'needs a pointer scrutinee')

    def test_duplicate_binding_name(self):
        self.assertCompileError("""
fn main {} {
    let x: ?i32 = 1
    let some{ value } = x else { return }
    let some{ value } = x else { return }
}
""", 'already declared')


class IfNull(Base):
    """`e ifnull x`: e's value if it has one, else x."""

    FIND = """
fn find { xs: []i32, want: i32 } -> ?usize {
    let mut i: usize = 0
    while i < xs.len {
        if xs[i] == want { return i }
        i = i + 1
    }
    return null
}
"""

    def test_default(self):
        self.assertOutput(self.FIND + """
fn main { mut io: Io } {
    let xs = [3, 5, 7]
    io::println_u64{ &io, n = find{ xs = xs[..], want = 5 } ifnull 99 }
    io::println_u64{ &io, n = find{ xs = xs[..], want = 4 } ifnull 99 }
}
""", '1\n99\n')

    def test_default_only_evaluated_when_null(self):
        self.assertOutput("""
fn loud { mut io: Io } -> i32 {
    io::println{ &io, s = "loud" }
    return 0
}
fn main { mut io: Io } {
    let a: ?i32 = 5
    let b: ?i32 = null
    io::println_i64{ &io, n = a ifnull loud{ &io } }
    io::println_i64{ &io, n = b ifnull loud{ &io } }
}
""", '5\nloud\n0\n')

    def test_block_that_leaves(self):
        self.assertOutput(self.FIND + """
fn index_of { xs: []i32, want: i32 } -> i32 {
    let i = find{ xs, want } ifnull { return -1 }
    return @as(i32, i)
}
fn main { mut io: Io } {
    let xs = [3, 5, 7]
    io::println_i64{ &io, n = index_of{ xs = xs[..], want = 7 } }
    io::println_i64{ &io, n = index_of{ xs = xs[..], want = 8 } }
    let ys: [3]?i32 = [1, null, 3]
    let mut i: usize = 0
    while i < ys.len {
        let y = ys[i]
        i = i + 1
        io::println_i64{ &io, n = y ifnull { continue } }
    }
}
""", '2\n-1\n1\n3\n')

    def test_block_with_a_value(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let n: ?i32 = null
    io::println_i64{ &io, n = n ifnull { let k = 40; k + 2 } }
}
""", '42\n')

    def test_leaving_runs_defers(self):
        self.assertOutput("""
fn f { mut io: Io, x: ?i32 } {
    defer io::println_i64{ &io, n = 99 }
    let v = x ifnull { return }
    io::println_i64{ &io, n = v }
}
fn main { mut io: Io } {
    f{ &io, x = 5 }
    f{ &io, x = null }
}
""", '5\n99\n99\n')

    def test_chains_right_to_left(self):
        # `a ifnull b ifnull c` is `a ifnull (b ifnull c)`. An optional default gives an optional.
        self.assertOutput("""
fn main { mut io: Io } {
    let a: ?i32 = null
    let b: ?i32 = 8
    let c: ?i32 = null
    io::println_i64{ &io, n = a ifnull b ifnull 0 }
    io::println_i64{ &io, n = a ifnull c ifnull 0 }
    let d = a ifnull c
    io::println_bool{ &io, n = d == null }
}
""", '8\n0\ntrue\n')

    def test_expected_type(self):
        self.assertOutput("""
fn small {} -> ?i8 { return null }
fn main { mut io: Io } {
    let n: i64 = small{} ifnull 1000
    io::println_i64{ &io, n }
}
""", '1000\n')

    def test_nullable_pointer(self):
        self.assertOutput("""
fn first { xs: []i32 } -> ?*i32 {
    if xs.len == 0 { return null }
    return &xs[0]
}
fn main { mut io: Io } {
    let xs = [3, 5]
    let zero = 0
    io::println_i64{ &io, n = (first{ xs = xs[..] } ifnull { @panic() }).* }
    io::println_i64{ &io, n = (first{ xs = xs[..0] } ifnull &zero).* }
}
""", '3\n0\n')

    def test_precedence(self):
        # Tighter than comparison and `and`, looser than arithmetic.
        self.assertOutput("""
fn main { mut io: Io } {
    let n: ?i32 = null
    let m: ?i32 = 2
    io::println_i64{ &io, n = n ifnull 1 + 1 }
    io::println_i64{ &io, n = m ifnull 1 + 1 }
    io::println_bool{ &io, n = m ifnull 0 == 2 }
    let b: ?bool = null
    io::println_bool{ &io, n = b ifnull true and false }
    if n ifnull 0 < 1 { io::println{ &io, s = "cond" } }
    if b ifnull { true } { io::println{ &io, s = "block" } }
}
""", '2\n2\ntrue\nfalse\ncond\nblock\n')

    def test_needs_an_optional(self):
        for body, found, line, col in [
            ('let x = 5 ifnull 0', '{integer}', 2, 13),
            ('let n: ?i32 = null\n    let p = &n\n    let x = p ifnull 0', '*?i32', 4, 13),
            # A narrowed local is no longer optional.
            ('let n: ?i32 = 3\n    if n != null { let y = n ifnull 0 }', 'i32', 3, 28),
        ]:
            with self.assertRaises(CompileError) as cm:
                run('fn main {} {\n    %s\n}' % body)
            self.assertEqual((cm.exception.msg, cm.exception.pos[:2]),
                             ('`ifnull` needs an optional value, got ' + found, (line, col)), body)

    def test_default_of_another_type(self):
        self.assertCompileError("""
fn main {} {
    let n: ?i32 = null
    let x = n ifnull true
}
""", 'branches have different types: i32 and bool')

    def test_block_must_give_a_value_or_leave(self):
        self.assertCompileError("""
fn main {} {
    let n: ?i32 = null
    let x = n ifnull { }
}
""", 'this branch must end in a value, or leave')

    def test_needs_a_right_side(self):
        self.assertCompileError("""
fn main {} {
    let n: ?i32 = null
    let x = n ifnull
}
""", "expected an expression, found '}'")


class Errors(Base):
    """Declared errors, `!T` with inferred error sets, `try`, `iferr` and matches on errors
    (spec §8, Errors)."""

    PARSE = """
namespace parse {
    error empty
    error bad_digit{ at: usize }
    error too_big
}

fn number { s: []u8 } -> !u64 {
    if s.len == 0 { return parse::empty }
    let mut n: u64 = 0
    let mut i: usize = 0
    while i < s.len {
        if s[i] < '0' or s[i] > '9' { return parse::bad_digit{ at = i } }
        if n > 100000 { return parse::too_big }
        n = n * 10 + @as(u64, s[i] - '0')
        i = i + 1
    }
    return n
}

fn show { mut io: Io, r: !u64 } {
    let mut mem: [256]u8 = [0; 256]
    let mut heap = arena::new{ buf = mem[..] }
    let mut b = utf8::builder{ realloc = arena::alloc, &heap }
    let ok = match r {
        ok{ value }  => { @fmt(&b, "ok {}", value) }
        err{ error } => { @fmt(&b, "err {}", error) }
    }
    if ok { io::println{ &io, s = utf8::view{ b } } }
}
"""

    def test_return_and_match(self):
        self.assertOutput(self.PARSE + """
fn main { mut io: Io } {
    show{ &io, r = number{ s = "42" } }
    show{ &io, r = number{ s = "" } }
    show{ &io, r = number{ s = "4x2" } }
    show{ &io, r = number{ s = "99999999" } }
}
""", 'ok 42\nerr parse::empty\nerr parse::bad_digit{ at = 1 }\nerr parse::too_big\n')

    def test_try_passes_the_error_up(self):
        self.assertOutput(self.PARSE + """
fn sum { a: []u8, b: []u8 } -> !u64 {
    let x = try number{ s = a }
    return x + try number{ s = b }
}
fn main { mut io: Io } {
    show{ &io, r = sum{ a = "40", b = "2" } }
    show{ &io, r = sum{ a = "40", b = "-" } }
    show{ &io, r = sum{ a = "", b = "-" } }
}
""", 'ok 42\nerr parse::bad_digit{ at = 0 }\nerr parse::empty\n')

    def test_try_runs_defers(self):
        self.assertOutput(self.PARSE + """
fn f { mut io: Io, s: []u8 } -> !u64 {
    defer io::println{ &io, s = "defer" }
    let n = try number{ s }
    io::println{ &io, s = "parsed" }
    return n
}
fn main { mut io: Io } {
    show{ &io, r = f{ &io, s = "7" } }
    show{ &io, r = f{ &io, s = "" } }
}
""", 'parsed\ndefer\nok 7\ndefer\nerr parse::empty\n')

    def test_iferr(self):
        self.assertOutput(self.PARSE + """
fn or_neg { s: []u8 } -> i64 {
    let n = number{ s } iferr { return -1 }
    return @as(i64, n)
}
fn main { mut io: Io } {
    io::println_u64{ &io, n = number{ s = "12" } iferr 0 }
    io::println_u64{ &io, n = number{ s = "1x" } iferr 0 }
    io::println_i64{ &io, n = or_neg{ s = "" } }
    io::println_u64{ &io, n = number{ s = "" } iferr number{ s = "x" } iferr 5 }
    let at = number{ s = "12x" } iferr err{ error } {
        match error {
            parse::bad_digit{ at } => { @as(u64, at) }
            else => { 0 }
        }
    }
    io::println_u64{ &io, n = at }
}
""", '12\n0\n-1\n5\n2\n')

    def test_errors_listed_beside_ok(self):
        self.assertOutput(self.PARSE + """
fn kind { s: []u8 } -> i32 {
    return match number{ s } {
        ok                 => { 0 }
        parse::empty       => { 1 }
        parse::bad_digit | parse::too_big => { 2 }
    }
}
fn rest { s: []u8 } -> i32 {
    match number{ s } {
        ok{ value }    => { return @as(i32, value) }
        parse::empty   => { return -1 }
        err{ error }   => {
            return match error { parse::too_big => { -3 } else => { -2 } }
        }
    }
}
fn main { mut io: Io } {
    io::println_i64{ &io, n = kind{ s = "5" } }
    io::println_i64{ &io, n = kind{ s = "" } }
    io::println_i64{ &io, n = kind{ s = "x" } }
    io::println_i64{ &io, n = rest{ s = "5" } }
    io::println_i64{ &io, n = rest{ s = "" } }
    io::println_i64{ &io, n = rest{ s = "x" } }
    io::println_i64{ &io, n = rest{ s = "1234567" } }
}
""", '0\n1\n2\n5\n-1\n-2\n-3\n')

    def test_sets_through_recursion(self):
        # even fails with a, odd with b, and each passes the other's up: both sets are {a, b},
        # so listing a and b is exhaustive.
        self.assertOutput("""
error a
error b{ n: i32 }
fn even { n: i32 } -> !bool {
    if n < 0 { return a }
    if n == 0 { return true }
    return try odd{ n = n - 1 }
}
fn odd { n: i32 } -> !bool {
    if n > 100 { return b{ n } }
    if n == 0 { return false }
    return try even{ n = n - 1 }
}
fn main { mut io: Io } {
    let ns = [4, 7, -1, 300]
    let mut i: usize = 0
    while i < ns.len {
        match even{ n = ns[i] } {
            ok{ value } => { io::println_bool{ &io, n = value } }
            a           => { io::println{ &io, s = "a" } }
            b{ n }      => { io::println_i64{ &io, n } }
        }
        i = i + 1
    }
}
""", 'true\nfalse\na\n299\n')

    def test_into_a_larger_set(self):
        # An error keeps its payload when it joins a set that numbers it differently.
        self.assertOutput("""
error x
error y{ k: u8, m: i64 }
error z
fn only_y {} -> !i32 { return y{ k = 7, m = -9 } }
fn generic(T) { xs: []T } -> !T {
    if xs.len == 0 { return z }
    return xs[0]
}
fn mixed { which: i32 } -> !i32 {
    if which == 0 { return x }
    if which == 1 { return only_y{} }
    return try generic{ xs = slice::empty(i32){} }
}
fn main { mut io: Io } {
    let mut mem: [512]u8 = [0; 512]
    let mut heap = arena::new{ buf = mem[..] }
    let mut b = utf8::builder{ realloc = arena::alloc, &heap }
    let mut i = 0
    while i < 3 {
        match mixed{ which = i } {
            ok => {}
            err{ error } => { _ = @fmt(&b, "{} ", error) }
        }
        i = i + 1
    }
    io::println{ &io, s = utf8::view{ b } }
}
""", 'x y{ k = 7, m = -9 } z \n')

    def test_bare_result(self):
        self.assertOutput("""
error closed
fn close { fail: bool } -> ! {
    if fail { return closed }
}
fn both { fail: bool } -> ! {
    try close{ fail = false }
    try close{ fail }
    return
}
fn main { mut io: Io } -> i32 {
    both{ fail = false } iferr { return 1 }
    io::println{ &io, s = "closed" }
    match both{ fail = true } {
        ok     => { io::println{ &io, s = "no" } }
        closed => { io::println{ &io, s = "failed" } }
    }
    both{ fail = true } iferr err{ error } { return 3 }
    return 0
}
""", 'closed\nfailed\n')

    def test_any_error(self):
        # `error`, and `!T` outside a function's own result, hold any error.
        self.assertOutput(self.PARSE + """
error other
struct Last { r: !u64 }
fn report { mut io: Io, e: error } {
    match e {
        parse::empty => { io::println{ &io, s = "empty" } }
        else         => { io::println{ &io, s = "something else" } }
    }
}
fn main { mut io: Io } {
    let last = Last{ r = number{ s = "" } }
    match last.r {
        ok => {}
        err{ error } => { report{ &io, e = error } }
    }
    report{ &io, e = other }
    let e: error = parse::too_big
    report{ &io, e }
}
""", 'empty\nsomething else\nsomething else\n')

    def test_let_else(self):
        self.assertOutput(self.PARSE + """
fn main { mut io: Io } -> i32 {
    let ok{ value } = number{ s = "8" } else err{ error } { return 1 }
    io::println_u64{ &io, n = value }
    let ok{ value = v } = number{ s = "" } else { return 2 }
    return 0
}
""", '8\n')

    def test_errors_in_namespaces(self):
        # Inside its namespace an error needs no path.
        self.assertOutput("""
namespace fsx {
    error not_found
    fn open { name: []u8 } -> !i32 {
        if name.len == 0 { return not_found }
        return 3
    }
    fn missing { name: []u8 } -> bool {
        return match open{ name } { ok => { false } not_found => { true } }
    }
}
fn main { mut io: Io } {
    io::println_bool{ &io, n = fsx::missing{ name = "" } }
    io::println_bool{ &io, n = fsx::missing{ name = "f" } }
}
""", 'true\nfalse\n')

    def test_pointers_in_payloads(self):
        # A payload may hold pointers (§8, Errors): here text from literals, and a view into the
        # caller's bytes. `try number{ s = buf[..] }` passes up only parse's errors, whose
        # payloads hold no pointer, so it may take a local's address although `bad`'s holds one.
        self.assertOutput(self.PARSE + r'''
error bad{ text: []u8 }
error named{ c: c::String, u: utf8::String }
fn head { s: []u8 } -> !u64 {
    if s[0] == 'x' { return bad{ text = s[0..3] } }
    return s.len
}
fn lookup { have: bool } -> !i32 {
    if not have { return named{ c = "glCreateShader", u = "h\xc3\xa9llo" } }
    return 1
}
fn sum { s: []u8 } -> !u64 {
    let buf: [3]u8 = ['1', '2', '3']
    let n = try number{ s = buf[..] }
    return n + s.len
}
fn main { mut io: Io } {
    match lookup{ have = false } {
        ok => {}
        named{ c, u } => {
            io::println{ &io, s = utf8::of{ chars = c::bytes{ s = c } } }
            io::println{ &io, s = u }
        }
    }
    let input: [5]u8 = ['x', 'y', 'z', 'z', 'y']
    match head{ s = input[..] } {
        ok{ value } => { io::println_u64{ &io, n = value } }
        bad{ text } => { io::println{ &io, s = utf8::of{ chars = text } } }
    }
    io::println_u64{ &io, n = sum{ s = "ab" } iferr 0 }
}
''', 'glCreateShader\nh\u00e9llo\nxyz\n125\n')

    def test_compile_errors(self):
        for body, msg, pos in [
            ('fn main {} -> i32 { match number{ s = "1" } { ok{ value } => { return 1 } parse::empty => { return 2 } } }',
             "match isn't exhaustive: missing parse::bad_digit, parse::too_big", (1, 21)),
            ('error other\nfn main {} -> i32 { match number{ s = "1" } { ok => { return 1 } other => { return 2 } err => { return 3 } } }',
             "error `other` can't happen here: this fails only with parse::empty, parse::bad_digit, parse::too_big", (2, 66)),
            ('fn main {} -> i32 { match number{ s = "1" } { ok => { return 1 } parse::empty => { return 2 } parse::bad_digit => { return 3 } parse::too_big => { return 4 } else => { return 5 } } }',
             '`else` is unreachable: every error is already listed', (1, 159)),
            ('fn main {} -> i32 { match number{ s = "1" } { parse::empty => { return 2 } else => { return 5 } } }',
             'a match that lists errors must list `ok` too', (1, 21)),
            ('fn main {} -> i32 { match number{ s = "1" } { ok => { return 1 } } }',
             "match isn't exhaustive: missing err", (1, 21)),
            ('fn main {} -> i32 {\n    let n = try number{ s = "1" }\n    return 0\n}',
             '`try` passes an error up: it needs a function that returns `!T`, not i32', (2, 13)),
            ('fn f {} -> !i32 { return try 5 }\nfn main {} {}', '`try` needs a `!T` value, got {integer}', (1, 30)),
            ('fn main {} { number{ s = "1" } }', 'the result of `number` (!u64) is unused', (1, 20)),
            ('fn main {} { let x = 5 iferr 0 }', '`iferr` needs a `!T` value, got {integer}', (1, 22)),
            ('fn f {} -> !i32 {\n    defer { _ = try number{ s = "1" } }\n    return 1\n}\nfn main {} {}',
             'cannot `try` in a defer: it may return', (2, 17)),
            ('fn g {} -> !u64 { return 1 }\nfn main {} {\n    let mut r = number{ s = "1" }\n    r = g{}\n}',
             'expected !u64 failing with the errors of `number`, got one failing with the errors of `g`', (4, 10)),
            ('fn main {} { let f: fn{ s: []u8 } -> !u64 = number }',
             "a function whose `!T` fails with its body's errors can't be a value of type fn{ s: []u8 } -> !u64", (1, 45)),
            ('fn f {} -> !i32 { return parse::bad_digit }\nfn main {} {}',
             'error `parse::bad_digit` has a payload; construct it with `parse::bad_digit{ ... }`', (1, 26)),
            ('fn f {} -> !i32 { return parse::empty{} }\nfn main {} {}',
             'error `parse::empty` has no payload; write it without braces', (1, 38)),
            ('error ok\nfn main {} {}', "an error can't be named `ok`", (1, 7)),
            ('error e{ r: !i32 }\nfn main {} {}', "error `e`'s field `r` can't hold !i32: a payload holds no `!T` or error", (1, 10)),
            # An error is a value for the escape check (§14): returning one, or passing one up
            # with `try`, that holds the address of a local is an error.
            ('error bad{ text: []u8 }\nfn f {} -> !u64 {\n    let buf: [4]u8 = [1; 4]\n    return bad{ text = buf[..] }\n}\nfn main {} {}',
             'returned value holds the address of local `buf`', (4, 5)),
            # g's set, known only once the sets are inferred, holds an error with a slice.
            ('error bad{ text: []u8 }\nfn g { s: []u8 } -> !u64 {\n    if s.len == 0 { return bad{ text = s } }\n    return 1\n}\n'
             'fn f {} -> !u64 {\n    let buf: [4]u8 = [1; 4]\n    let t = try g{ s = buf[..] }\n    return t\n}\nfn main {} {}',
             '`try` would return an error that may hold the address of local `buf`', (8, 13)),
            ('error bad{ text: []u8 }\nfn g { s: []u8 } -> !u64 {\n    if s.len == 0 { return bad{ text = s } }\n    return 1\n}\n'
             'fn f {} -> !u64 {\n    let buf: [4]u8 = [1; 4]\n    return g{ s = buf[..] }\n}\nfn main {} {}',
             'returned value holds the address of local `buf`', (8, 5)),
            ('extern fn foo {} -> !i32\nfn main {} {}', "extern fn `foo` can't return !i32", (1, 21)),
            ('const C: !i32 = 1\nfn main {} {}', "a const can't hold a `!T` or an error", (1, 10)),
            ('fn main {} -> i32 { match number{ s = "1" } { ok => { return 1 } q::empty => { return 2 } else => { return 3 } } }',
             'unknown type or namespace `q`', (1, 66)),
        ]:
            with self.assertRaises(CompileError, msg=body) as cm:
                run(self.PARSE + body)
            line = self.PARSE.count('\n')
            self.assertIn(msg, cm.exception.msg, body)
            self.assertEqual(cm.exception.pos[:2], (pos[0] + line, pos[1]), body)

    def test_error_needs_a_name(self):
        # `error` begins a declaration only before a name: elsewhere it is a name itself.
        self.assertOutput("""
fn error { n: i32 } -> i32 { return n + 1 }
fn main { mut io: Io } {
    let error = error{ n = 1 }
    io::println_i64{ &io, n = error }
}
""", '2\n')


class Defer(Base):
    def test_order_and_return(self):
        self.assertOutput("""
fn say { mut io: Io, n: i64 } { io::println_i64{ &io, n } }
fn early { mut io: Io, stop: bool } -> i64 {
    defer say{ &io, n = 1 }
    defer { say{ &io, n = 2 }; say{ &io, n = 3 } }
    if stop { return 10 }
    say{ &io, n = 4 }
    return 20
}
fn main { mut io: Io } {
    say{ &io, n = early{ &io, stop = true } }
    say{ &io, n = early{ &io, stop = false } }
}
""", '2\n3\n1\n10\n4\n2\n3\n1\n20\n')

    def test_runs_at_exit_of_its_block(self):
        self.assertOutput("""
fn say { mut io: Io, n: i64 } { io::println_i64{ &io, n } }
fn main { mut io: Io } {
    if true {
        defer say{ &io, n = 1 }
        say{ &io, n = 2 }
    }
    say{ &io, n = 3 }
}
""", '2\n1\n3\n')

    def test_loops(self):
        self.assertOutput("""
fn say { mut io: Io, n: i64 } { io::println_i64{ &io, n } }
fn main { mut io: Io } {
    let mut i = 0
    while i < 3 {
        defer say{ &io, n = 100 + i }     // evaluated at exit, after i changes
        i = i + 1
        if i == 2 { continue }
        if i == 3 { break }
        say{ &io, n = i }
    }
}
""", '1\n101\n102\n103\n')

    def test_expression_branches(self):
        self.assertOutput("""
fn say { mut io: Io, n: i64 } { io::println_i64{ &io, n } }
fn branch { mut io: Io, o: ?i64 } -> i64 {
    let v = match o {
        null => { defer say{ &io, n = -1 }; return 0 }
        some{ value } => { defer say{ &io, n = -2 }; value * 2 }
    }
    return v
}
fn main { mut io: Io } {
    say{ &io, n = branch{ &io, o = null } }
    say{ &io, n = branch{ &io, o = 21 } }
}
""", '-1\n0\n-2\n42\n')

    def test_free_list(self):
        self.assertOutput("""
fn total { mut heap: arena::Arena, n: i32 } -> i64 {
    let mut xs = list::new(i32){ realloc = arena::alloc, &heap }
    defer list::free{ list = &xs}
    let mut i = 0
    while i < n {
        if not list::push{ list = &xs, item = i } { return -1 }
        i = i + 1
    }
    let mut sum: i64 = 0
    let mut j: usize = 0
    while j < xs.len {
        sum = sum + list::at{ list = xs, i = j }.*
        j = j + 1
    }
    return sum
}
fn main { mut io: Io } {
    let mut mem: [4096]u8
    let mut heap = arena::new{ buf = mem[..] }
    io::println_i64{ &io, n = total{ &heap, n = 10 } }
}
""", '45\n')

    def test_assignment_and_loop_inside(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let mut n = 0
    defer n = n + 1
    defer {
        let mut i = 0
        while true {
            i = i + 1
            if i == 3 { break }
        }
        io::println_i64{ &io, n = n + i }
    }
}
""", '3\n')

    def test_not_run_on_panic(self):
        out = io.StringIO()
        with self.assertRaises(Panic):
            run_source("""
fn main { mut io: Io } {
    defer io::println_i64{ &io, n = 1 }
    @panic()
}
""", out=out)
        self.assertEqual(out.getvalue(), '')

    def test_no_return(self):
        self.assertCompileError("""
fn f {} -> i32 {
    defer { return 1 }
    return 2
}
fn main { mut io: Io } { }
""", 'cannot `return` from a defer')

    def test_no_break_out(self):
        self.assertCompileError('fn main { mut io: Io } { while true { defer { break } } }',
                                '`break` outside a loop in this defer')

    def test_no_assign_once_local(self):
        self.assertCompileError('fn main { mut io: Io } { let x: i32; defer { x = 1 }; x = 2 }',
                                'cannot assign `x` in a defer')

    def test_checked_where_written(self):
        self.assertCompileError("""
fn main { mut io: Io } {
    let x: i32
    defer io::println_i64{ &io, n = x }
    x = 2
}
""", '`x` may be read before it is assigned')

    def test_takes_call_assignment_or_block(self):
        self.assertCompileError('fn main { mut io: Io } { defer let x = 1 }',
                                '`defer` takes a call, an assignment, `_ = e` or a block')


FS_MAIN = """
fn main { mut io: Io, mut fs: Fs, args: Args } -> i32 {
    let mut mem: [65536]u8
    let mut heap = arena::new{ buf = mem[..] }
%s
}
"""


def show_error():
    return """
fn show { mut io: Io, e: error } {
    let code = match e {
        fs::not_found => { 1 } fs::permission_denied => { 2 } fs::is_directory => { 3 } fs::exists => { 4 }
        fs::not_directory => { 5 } fs::bad_file => { 6 } fs::out_of_memory => { 7 } fs::other => { 8 }
        else => { 9 }
    }
    io::println_i64{ &io, n = code }
}
"""


class Fs(Base):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.dir, name)

    def run_fs(self, body, args=(), extra=''):
        out = io.StringIO()
        code = run_source(extra + FS_MAIN % body, out=out, args=list(args))
        return out.getvalue(), code

    def test_list_and_make_dir(self):
        for name in ['b.txt', 'a.ctx', 'c']:
            with open(self.path(name), 'w') as f:
                f.write('x')
        out, code = self.run_fs("""
    io::println_bool{ &io, n = match fs::make_dir{ &fs, path = args[1] } { ok => { true } err => { false } } }
    let again = match fs::make_dir{ &fs, path = args[1] } { ok => { false } fs::exists => { true } else => { false } }
    io::println_bool{ &io, n = again }
    let names = fs::list{ &fs, &heap, realloc = arena::alloc, path = args[0] } iferr { return 1 }
    let mut i: usize = 0
    while i < names.len {
        io::println{ &io, s = utf8::of{ chars = names[i] } }
        i = i + 1
    }
    match fs::list{ &fs, &heap, realloc = arena::alloc, path = args[2] } {
        ok            => { return 2 }
        fs::not_found => { return 0 }
        else          => { return 3 }
    }
""", [self.dir, self.path('sub'), self.path('missing')])
        self.assertEqual((out, code), ('true\ntrue\na.ctx\nb.txt\nc\nsub\n', 0))

    def test_read_all_and_write_all(self):
        src, dst = self.path('in.txt'), self.path('out.txt')
        with open(src, 'wb') as f:
            f.write(b'hello\nfrom a file\n')
        out, code = self.run_fs("""
    let text = fs::read_all{ &fs, &heap, realloc = arena::alloc, path = args[0] } iferr { return 1 }
    io::print{ &io, s = utf8::of{ chars = text } }
    io::println_u64{ &io, n = fs::write_all{ &fs, path = args[1], bytes = text } iferr { return 2 } }
    io::println_u64{ &io, n = fs::size{ &fs, path = args[1] } iferr { return 3 } }
    return 0
""", [src, dst])
        self.assertEqual((out, code), ('hello\nfrom a file\n18\n18\n', 0))
        with open(dst, 'rb') as f:
            self.assertEqual(f.read(), b'hello\nfrom a file\n')

    def test_read_all_large_and_empty(self):
        big, empty = self.path('big.bin'), self.path('empty.bin')
        data = bytes(i % 251 for i in range(10000))
        with open(big, 'wb') as f:
            f.write(data)
        open(empty, 'wb').close()
        out, _ = self.run_fs("""
    let a = fs::read_all{ &fs, &heap, realloc = arena::alloc, path = args[0] } iferr { return 1 }
    io::println_u64{ &io, n = a.len }
    let mut sum: u64 = 0
    let mut i: usize = 0
    while i < a.len {
        sum = sum + a[i]
        i = i + 1
    }
    io::println_u64{ &io, n = sum }
    let b = fs::read_all{ &fs, &heap, realloc = arena::alloc, path = args[1] } iferr { return 1 }
    io::println_u64{ &io, n = b.len }
    return 0
""", [big, empty])
        self.assertEqual(out, f'10000\n{sum(data)}\n0\n')

    def test_open_read_write_close(self):
        p = self.path('f.txt')
        out, _ = self.run_fs("""
    let path = args[0]
    let w = fs::open{ &fs, path, mode = fs::Mode::create } iferr { return 1 }
    let a = "abc"
    _ = fs::write{ &fs, file = w, bytes = a[..] }
    io::println_bool{ &io, n = match fs::close{ &fs, file = w } { ok => { true } err => { false } } }
    match fs::open{ &fs, path, mode = fs::Mode::append } {
        ok{ value } => {
            let d = "de"
            _ = fs::write{ &fs, file = value, bytes = d[..] }
        }
        err => {}
    }
    let r = fs::open{ &fs, path, mode = fs::Mode::read } iferr { return 1 }
    defer _ = fs::close{ &fs, file = r }
    let mut buf: [2]u8
    let mut total: usize = 0
    while true {
        let n = fs::read{ &fs, file = r, into = buf[..] } iferr { return 1 }
        if n == 0 { break }
        io::print{ &io, s = utf8::of{ chars = buf[..][..n] } }
        total = total + n
    }
    io::newline{ &io }
    io::println_u64{ &io, n = total }
    return 0
""", [p])
        self.assertEqual(out, 'true\nabcde\n5\n')

    def test_errors(self):
        existing, missing = self.path('there.txt'), self.path('missing.txt')
        open(existing, 'wb').close()
        out, _ = self.run_fs("""
    let there = args[0]
    let missing = args[1]
    let dir = args[2]
    let nested = args[3]
    match fs::open{ &fs, path = missing, mode = fs::Mode::read } { ok => {} err{ error } => { show{ &io, e = error } } }
    match fs::open{ &fs, path = there, mode = fs::Mode::create } { ok => {} err{ error } => { show{ &io, e = error } } }
    match fs::read_all{ &fs, &heap, realloc = arena::alloc, path = dir } { ok => {} err{ error } => { show{ &io, e = error } } }
    fs::close{ &fs, file = fs::File{ id = 999 } } iferr err{ error } { show{ &io, e = error } }
    fs::remove{ &fs, path = missing } iferr err{ error } { show{ &io, e = error } }
    io::println_bool{ &io, n = match fs::remove{ &fs, path = there } { ok => { true } err => { false } } }
    io::println_bool{ &io, n = match fs::size{ &fs, path = there } { ok => { false } err => { true } } }
    match fs::open{ &fs, path = nested, mode = fs::Mode::write } { ok => {} err{ error } => { show{ &io, e = error } } }
    let empty = slice::empty(u8){}
    match fs::size{ &fs, path = empty } { ok => {} err{ error } => { show{ &io, e = error } } }
    return 0
""", [existing, missing, self.dir, os.path.join(self.dir, 'no_such_dir', 'x.txt')], show_error())
        self.assertEqual(out, '1\n4\n3\n6\n1\ntrue\ntrue\n1\n1\n')

    def test_read_all_out_of_memory(self):
        p = self.path('big.bin')
        with open(p, 'wb') as f:
            f.write(bytes(5000))
        out, _ = self.run_fs("""
    let mut small: [100]u8
    let mut tiny = arena::new{ buf = small[..] }
    match fs::read_all{ &fs, heap = &tiny, realloc = arena::alloc, path = args[0] } { ok => {} err{ error } => { show{ &io, e = error } } }
    return 0
""", [p], show_error())
        self.assertEqual(out, '7\n')

    def test_exit_code_and_args(self):
        out, code = self.run_fs("""
    io::println_u64{ &io, n = args.len }
    let a = utf8::of{ chars = args[1] }
    io::println{ &io, s = a }
    io::println_u64{ &io, n = args[2].len }
    return 3
""", ['x', 'second', ''])
        self.assertEqual((out, code), ('3\nsecond\n0\n', 3))

    def test_no_args(self):
        out, code = self.run_fs('    io::println_u64{ &io, n = args.len }\n    return 0')
        self.assertEqual((out, code), ('0\n', 0))

    def test_main_without_return_exits_zero(self):
        self.assertEqual(run_source('fn main { mut io: Io } { }', out=io.StringIO()), 0)

    def test_main_return_type(self):
        self.assertCompileError('fn main { mut io: Io } -> i64 { return 0 }', '`main` can only return i32')

    def test_main_args_type(self):
        self.assertCompileError('fn main { args: []u8 } { }', '`args` must have type')

    def test_main_args_long_spelling(self):
        src = 'fn main { args: [][]u8 } -> i32 { return @as(i32, args.len) }'
        self.assertEqual(run_source(src, out=io.StringIO(), args=['a', 'b']), 2)

    def test_main_args_with_user_args_type(self):
        src = 'struct Args { n: i32 }\nfn main { args: [][]u8 } { }'
        self.assertEqual(run_source(src, out=io.StringIO()), 0)

    def test_main_field_must_be_capability(self):
        self.assertCompileError('fn main { n: i32 } { }', 'must have a capability type')

    def test_fs_needs_capability(self):
        self.assertCompileError("""
fn helper { path: []u8 } { fs::remove{ path } }
fn main { mut fs: Fs } { }
""", 'missing `fs`')


MEM_MAIN = """
fn main { mut io: Io, mut mem: Mem } -> i32 {
%s
}
"""


class Mem(Base):
    def run_mem(self, body, extra=''):
        out = io.StringIO()
        code = run_source(extra + MEM_MAIN % body, out=out)
        return out.getvalue(), code

    def test_pages_256_mib(self):
        out, code = self.run_mem("""
    let some{ value = buf } = mem::pages{ &mem, size = 268435456 } else { return 1 }
    io::println_u64{ &io, n = buf.len }
    io::println_u64{ &io, n = @addr(&buf[0]) % 4096 }
    io::println_u64{ &io, n = buf[buf.len - 1] }
    buf[buf.len - 1] = 7
    io::println_u64{ &io, n = buf[buf.len - 1] }
    return 0
""")
        self.assertEqual((out, code), ('268435456\n0\n0\n7\n', 0))

    def test_pages_round_up_and_do_not_overlap(self):
        out, _ = self.run_mem("""
    let some{ value = a } = mem::pages{ &mem, size = 10 } else { return 1 }
    let some{ value = b } = mem::pages{ &mem, size = 5000 } else { return 1 }
    io::println_u64{ &io, n = a.len }
    io::println_u64{ &io, n = b.len }
    slice::fill{ s = a, v = 1 }
    slice::fill{ s = b, v = 2 }
    io::println_u64{ &io, n = a[a.len - 1] }
    io::println_bool{ &io, n = @addr(&b[0]) > @addr(&a[a.len - 1]) or @addr(&a[0]) > @addr(&b[b.len - 1]) }
    return 0
""")
        self.assertEqual(out, '4096\n8192\n1\ntrue\n')

    def test_pages_zero_and_too_large(self):
        # 2^62 bytes is more than any 64-bit OS maps; the largest usize can't be rounded up to
        # a page at all.
        out, _ = self.run_mem("""
    let some{ value = z } = mem::pages{ &mem, size = 0 } else { return 1 }
    io::println_u64{ &io, n = z.len }
    if mem::pages{ &mem, size = 4611686018427387904 } == null { io::println_i64{ &io, n = -1 } }
    if mem::pages{ &mem, size = 18446744073709551615 } == null { io::println_i64{ &io, n = -2 } }
    return 0
""")
        self.assertEqual(out, '0\n-1\n-2\n')

    def test_pages_are_not_stack(self):
        # Memory from pages doesn't extend the stack: deep recursion still overflows.
        with self.assertRaises(Panic) as cm:
            self.run_mem("""
    _ = mem::pages{ &mem, size = 67108864 }
    return down{ n = 0 }
""", extra='fn down { n: i32 } -> i32 { let big: [1048576]u8 = [0; 1048576]; if (n == 20) { return 0 }; return down{ n = n + 1 } + @as(i32, big[@as(usize, n)]) }\n')
        self.assertIn('stack overflow', cm.exception.msg)

    def test_pages_need_capability(self):
        self.assertCompileError("""
fn grab {} { mem::pages{ size = 10 } }
fn main { mut mem: Mem } { }
""", 'missing `mem`')

    def test_alloc_new_and_free(self):
        out, _ = self.run_mem("""
    let some{ value = buf } = mem::pages{ &mem, size = 4096 } else { return 1 }
    let mut heap = arena::new{ buf }
    let mut head: ?*mut Node = null
    let mut i: i64 = 1
    while i <= 4 {
        let some{ value = n } = alloc::new{ realloc = arena::alloc, &heap, value = Node{ v = i, next = head } } else { return 2 }
        head = n
        i = i + 1
    }
    let mut total: i64 = 0
    let mut cur = head
    while true {
        let some{ value = n } = cur else { break }
        total = total * 10 + n.v
        cur = n.next
    }
    io::println_i64{ &io, n = total }
    let some{ value = h } = head else { return 3 }
    alloc::free{ realloc = arena::alloc, &heap, p = h }
    return 0
""", extra='struct Node { v: i64, next: ?*mut Node }\n')
        self.assertEqual(out, '4321\n')

    def test_alloc_new_out_of_memory(self):
        out, _ = self.run_mem("""
    let mut buf: [16]u8
    let mut heap = arena::new{ buf = buf[..] }
    let a = alloc::new{ realloc = arena::alloc, &heap, value = [1, 2, 3, 4, 5] }
    io::println_bool{ &io, n = a == null }
    let b = alloc::new{ realloc = arena::alloc, &heap, value = 5 }
    io::println_bool{ &io, n = b == null }
    return 0
""")
        self.assertEqual(out, 'true\nfalse\n')

    def test_alloc_new_zero_sized(self):
        with self.assertRaises(Panic) as cm:
            self.run_mem("""
    let mut buf: [16]u8
    let mut heap = arena::new{ buf = buf[..] }
    _ = alloc::new{ realloc = arena::alloc, &heap, value = Empty{} }
    return 0
""", extra='struct Empty {}\n')
        self.assertIn('alloc::new: T is zero-sized', cm.exception.msg)

    def test_builder_push_floats(self):
        out, _ = self.run_mem("""
    let some{ value = buf } = mem::pages{ &mem, size = 4096 } else { return 1 }
    let mut heap = arena::new{ buf }
    let mut b = utf8::builder{ realloc = arena::alloc, &heap }
    _ = utf8::push_f64{ &b, n = 0.1 }
    _ = utf8::push_char{ &b, c = ' ' }
    _ = utf8::push_f32{ &b, n = 0.1 }
    _ = utf8::push_char{ &b, c = ' ' }
    _ = utf8::push_f64{ &b, n = 1e100 }
    io::println{ &io, s = utf8::view{ b } }
    let mut u = utf8::builder{ realloc = arena::alloc, &heap }
    _ = utf8::push_f64{ b = &u, n = -2.5 }
    _ = utf8::push_f32{ b = &u, n = 3.0 }
    io::println{ &io, s = utf8::view{ b = u } }
    return 0
""")
        self.assertEqual(out, '0.1 0.1 1e+100\n-2.53.0\n')


class PlatformLayers(Base):
    """std's platform layers (std/os/PLATFORM, spec §17), and standard output's buffer, which std
    fills and the runtime flushes."""

    def test_every_layer_checks(self):
        # A build checks only its own layer, so each is checked here from any machine, with the
        # C symbols it calls.
        import toolchain
        # Linux's and macOS's share std/os/posix.
        self.assertEqual(sorted(os.listdir(os.path.join(ROOT, 'std', 'os'))), sorted(toolchain.PLATFORMS + ('posix',)))
        d, files = toolchain.write_program([("""
fn main { mut io: Io, mut mem: Mem, mut fs: Fs } -> i32 {
    let mut line: [16]u8
    _ = io::read_line{ &io, into = line[..] }
    io::eprintln{ &io, s = "e" }
    let some{ value = buf } = mem::pages{ &mem, size = 1 } else { return 1 }
    io::println_u64{ &io, n = buf.len }
    let mut heap = arena::new{ buf = line[..] }
    let f = fs::open{ &fs, path = "x", mode = fs::Mode::create } iferr { return 1 }
    _ = fs::write{ &fs, file = f, bytes = "y" }
    _ = fs::close{ &fs, file = f }
    _ = fs::list{ &fs, &heap, realloc = arena::alloc, path = "." }
    return 0
}
""", 'main.ctx')])
        posix = ['write', 'read', 'aligned_alloc', 'memset', 'open', 'close', 'opendir', 'readdir']
        for platform, symbols in [('linux', posix + ['__errno_location']),
                                  ('macos', posix + ['__error']),
                                  ('windows', ['_write', '_read', 'VirtualAlloc', 'CreateFileW', 'FindFirstFileW'])]:
            c = os.path.join(d, f'{platform}.c')
            self.assertEqual(toolchain.ctxc_build(toolchain.native_ctxc(), c, list(files), cwd=d, platform=platform), (0, ''))
            with open(c, encoding='utf-8') as f:
                text = f.read()
            for s in symbols:
                self.assertIn(f'CTX_SYMBOL("{s}")', text, platform)

    def test_output_order(self):
        # Standard output is written out before standard error, and a panic writes out what is
        # left before its message.
        import subprocess
        from toolchain import build_sources
        exe, _ = build_sources([("""
fn main { mut io: Io } {
    io::print{ &io, s = "1" }
    io::eprint{ &io, s = "2" }
    io::print{ &io, s = "3" }
    io::eprint{ &io, s = "4" }
    io::print{ &io, s = "5" }
    @panic("6")
}
""", None)])
        r = subprocess.run([exe], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(r.returncode, 134)
        out = r.stdout.decode().replace('\r\n', '\n')
        self.assertTrue(out.startswith('12345') and out.endswith(': panic: 6\n'), out)


class IRDump(Base):
    """The typed IR (`ctxc ir`), and ctxc's reader and printer for it."""

    def ir(self, src):
        from toolchain import ir_sources
        return ir_sources([(src, None)])

    def test_widening_is_explicit(self):
        text = self.ir("""
fn f { x: i64 } -> i64 { return x }
fn main { mut io: Io } {
    let a: i32 = 5
    io::println_i64{ &io, n = f{ x = a } }
}
""")
        self.assertRegex(text, r'\(call \d+ \d+ \[\(0 \(widen \d+ \(local \d+ 1\)\)\)\]\)')

    def test_optional_and_narrowing(self):
        text = self.ir("""
fn main {} -> i32 {
    let x: ?i32 = 5
    if x != null { return x }
    return 0
}
""")
        self.assertIn('(let 0 (some ', text)
        self.assertIn('(notnull ', text)
        self.assertRegex(text, r'\(return \(payload \d+ \(local \d+ 0\) 1 0\)\)')

    def test_function_conversion(self):
        text = self.ir("""
fn g { a: i32 } -> i32 { return a }
fn main {} -> i32 {
    let h: fn{ a: i32, b: i32 } -> i32 = g
    return h{ a = 1, b = 2 }
}
""")
        self.assertRegex(text, r'\(let 0 \(fnconv \d+ \(fnref \d+ 1\)\)\)')
        self.assertIn('(dcall ', text)

    def test_generic_instances(self):
        text = self.ir("""
fn id(T) { x: T } -> T { return x }
fn main {} -> i32 {
    let a = id{ x = 1 }
    let b = id{ x = true }
    return a
}
""")
        self.assertIn('"id(i32)"', text)
        self.assertIn('"id(bool)"', text)

    def test_mut_field_is_a_pointer(self):
        text = self.ir("""
fn bump { mut n: i32 } { n = n + 1 }
fn main {} -> i32 {
    let mut n = 1
    bump{ &n }
    return n
}
""")
        self.assertRegex(text, r'\(set \(deref \d+ \(local \d+ 0\) \d+ \d+ \d+\)')
        self.assertIn('(addr ', text)

    def test_literal_views(self):
        text = self.ir("""
fn main { mut io: Io } {
    let b: []u8 = "abc"
    io::println{ &io, s = "hi" }
}
""")
        self.assertRegex(text, r'\(let 1 \(sbytes \d+ "abc"\)\)')
        self.assertRegex(text, r'\(struct \d+ \[\(0 \(sbytes \d+ "hi"\)\)\]\)')

    def test_loop_labels(self):
        text = self.ir("""
fn main { mut io: Io } {
    a: while true {
        b: while true {
            while true { continue b }
            if true { break b }
            break a
        }
    }
}
""")
        # A loop gets an id only if an inner loop's jump leaves or repeats it; a labeled jump to
        # the innermost loop is plain.
        self.assertIn('(continue 1)', text)
        self.assertIn('(break 2)', text)
        self.assertIn('(break)', text)
        self.assertRegex(text, r'\n    \} 1\)\n  \} 2\)')

    def test_examples_lower(self):
        from toolchain import ir_sources
        for path in ('examples/list.ctx', 'examples/wordcount.ctx', 'examples/json', 'examples/glfw/src'):
            self.assertIn('(main ', ir_sources(read_program(os.path.join(ROOT, path))))

    def test_ctxc_roundtrip(self):
        import tempfile
        text = self.ir("""
fn main { mut io: Io } -> i32 {
    let s = "a \\"quoted\\" \\n line"
    let v: []u8 = "a \\xff view"
    let x: f32 = 0.1
    let y = -2.5
    let n: i64 = -9223372036854775807 - 1
    let o: ?i32 = 3
    io::println_f64{ &io, n = x + y }
    return if (n < 0) { 1 } else { match (o) { null => { 0 } some{ value } => { value } } }
}
""")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'p.ir')
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(text)
            import subprocess
            from toolchain import native_ctxc
            r = subprocess.run([native_ctxc(), 'roundtrip', path], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.decode(), text)


@unittest.skipUnless(shutil.which('gcc') or shutil.which('zig'), 'needs a C compiler')
class CBackend(Base):
    """Programs that stress the C backend: evaluation order, defer, function values, numbers."""

    def both(self, src, args=(), stdin=b''):
        """(output, exit code or panic message). The expected values are what ctxi, the Python
        interpreter that was the reference until stage 8, gave."""
        out = io.BytesIO()
        try:
            code = run_source(src, out=out, args=list(args), inp=io.BytesIO(stdin))
        except Panic as e:
            code = 'panic: ' + e.msg
        return out.getvalue().decode(), code

    def test_literal_views(self):
        out, code = self.both(r"""
fn view {} -> []u8 { return "q\"?\\\x00\xff" }
fn main { mut io: Io } -> i32 {
    io::println{ &io, s = "caf\xc3\xa9" }
    let v = view{}
    io::println_u64{ &io, n = v.len }
    io::println_u64{ &io, n = v[5] }
    let e: []u8 = ""
    return @as(i32, e.len)
}
""")
        self.assertEqual((out, code), ('café\n6\n255\n', 0))

    def test_const_tables(self):
        out, code = self.both("""
const WORDS: [3][]u8 = ["fn", "let", "match"]
const NAMES: [2]utf8::String = ["zero", "caf\\xc3\\xa9"]
fn main { mut io: Io } -> i32 {
    io::println{ &io, s = NAMES[1] }
    return @as(i32, WORDS[2].len)
}
""")
        self.assertEqual((out, code), ('café\n', 5))

    def test_narrowed_fields(self):
        out, code = self.both("""
struct Inner { tag: ?i64 }
struct Node { kids: ?[]i32, inner: Inner }
fn tag { o: ?Node } -> i64 {
    if o == null or o.inner.tag == null { return 0 }
    let p = &o.inner.tag
    return o.inner.tag + p.*
}
fn main { mut io: Io } -> i32 {
    let ks = [3, 4]
    let n = Node{ kids = ks[..], inner = Inner{ tag = 5 } }
    io::println_i64{ &io, n = tag{ o = n } }
    io::println_i64{ &io, n = tag{ o = null } }
    if n.kids == null { return 1 }
    return n.kids[1]
}
""")
        self.assertEqual((out, code), ('10\n0\n', 4))

    def test_labeled_loops(self):
        out, code = self.both("""
fn main { mut io: Io } -> i32 {
    let mut i = 0
    let mut hits = 0
    outer:
    while i < 5 {
        i = i + 1
        defer {
            // copied to each exit of the body: its labels must not clash
            let mut k = 0
            inner: while true { while true { k = k + 1; if k == 2 { break inner } } }
            hits = hits + 100 * k / 2
        }
        let mut j = 0
        while j < 5 {
            j = j + 1
            if j == 2 { continue outer }
            if i == 4 { break outer }
            hits = hits + 1
        }
    }
    io::println_i64{ &io, n = hits }
    let d = if hits > 0 { 1 } else { 2 }
    top: while true {
        while true {
            let v = if d == 1 { break top } else { 5 }
            return v
        }
    }
    return i
}
""")
        self.assertEqual((out, code), ('403\n', 4))

    def test_evaluation_order(self):
        out, _ = self.both("""
fn bump { mut n: i32 } -> i32 { n = n + 1; return n }
fn pair { a: i32, b: i32 } -> i32 { return a * 10 + b }
fn main { mut io: Io } {
    let mut x = 1
    io::println_i64{ &io, n = x + bump{ n = &x } }             // 1 + 2
    io::println_i64{ &io, n = pair{ b = bump{ n = &x }, a = bump{ n = &x } } }
    let mut a = [0, 0, 0]
    a[@as(usize, bump{ n = &x } - 5)] = bump{ n = &x }             // value first, then the place
    io::println_i64{ &io, n = a[1] * 100 + a[2] }
}
""")
        self.assertEqual(out, '3\n43\n500\n')

    def test_defer_on_every_exit(self):
        out, _ = self.both("""
fn f { mut io: Io, n: i32 } -> i32 {
    defer io::println_i64{ &io, n = 100 }
    let mut i = 0
    while true {
        defer io::println_i64{ &io, n = i }
        i = i + 1
        if i == 2 { continue }
        if i == 3 { break }
    }
    let v = if n > 0 { return n } else { 7 }
    return v
}
fn main { mut io: Io } {
    io::println_i64{ &io, n = f{ &io, n = 5 } }
    io::println_i64{ &io, n = f{ &io, n = 0 } }
}
""")
        self.assertEqual(out, '1\n2\n3\n100\n5\n1\n2\n3\n100\n7\n')

    def test_function_values(self):
        out, _ = self.both("""
fn add { a: i32, b: i32 } -> i32 { return a + b }
fn one { a: i32 } -> i32 { return a }
fn apply { f: &fn{ a: i32 } -> i32, a: i32 } -> i32 { return f{ a } }
fn wide { f: fn{ a: i32, b: i32 } -> i32 } -> i32 { return f{ a = 3, b = 4 } }
fn main { mut io: Io } {
    let add2 = add{ b = 2, _ }
    io::println_i64{ &io, n = apply{ f = add2, a = 5 } }
    io::println_i64{ &io, n = apply{ f = one, a = 6 } }
    io::println_i64{ &io, n = wide{ f = one } }
    let g: fn{ a: i32, b: i32 } -> i32 = add
    let h = g{ a = 1, _ }
    io::println_i64{ &io, n = h{ b = 9 } }
}
""")
        self.assertEqual(out, '7\n6\n3\n10\n')

    def test_numbers(self):
        out, _ = self.both("""
fn main { mut io: Io } {
    let x: f32 = 0.1
    io::println_f32{ &io, n = x }
    io::println_f64{ &io, n = x }
    io::println_f64{ &io, n = 1e16 }
    io::println_f64{ &io, n = 0.0001 }
    io::println_f64{ &io, n = 0.00001 }
    io::println_f64{ &io, n = -2.5 / 0.0 }
    let big: i64 = -9223372036854775807 - 1
    io::println_i64{ &io, n = big % -1 }
    io::println_i64{ &io, n = -7 / 2 }
    io::println_u64{ &io, n = @wrap_mul(@as(u64, 3), 18446744073709551615) }
    io::println_i64{ &io, n = @trunc(i8, 300) }
    io::println_i64{ &io, n = @as(i64, 2.9) }
}
""")
        self.assertEqual(out, '0.1\n0.10000000149011612\n1e+16\n0.0001\n1e-05\n-inf\n0\n-3\n'
                              '18446744073709551613\n44\n2\n')

    def test_panics(self):
        for body, msg in [
            ('let a = [1, 2]\n    let i: usize = 2\n    io::println_i64{ &io, n = a[i] }',
             'index 2 out of bounds for length 2'),
            ('let x: i32 = 2147483647\n    io::println_i64{ &io, n = x + 1 }', 'integer overflow'),
            ('let z = 0\n    io::println_i64{ &io, n = 1 / z }', 'division by zero'),
            ('let f = 1e300\n    io::println_i64{ &io, n = @as(i32, f) }',
             '@as: 1e+300 is not representable in i32'),
            ('let n: i64 = -1\n    io::println_u64{ &io, n = @as(u32, n) }', '@as: -1 is not representable in u32'),
            ('@panic("bad \\"thing\\"")', 'bad "thing"'),
            ('let mut a: [3]u8\n    let s = a[..]\n    let i: usize = 3\n    s[i] = 1',
             'index 3 out of bounds for length 3'),
            ('let a: [3]u8 = [1, 2, 3]\n    let lo: usize = 2\n    let s = a[lo..1]', 'range 2..1 out of bounds for length 3'),
            ('let a: [3]u8 = [1, 2, 3]\n    let s = a[1..]\n    let t = s[..3]', 'range 0..3 out of bounds for length 2'),
        ]:
            with self.subTest(msg=msg):
                _, code = self.both('fn main { mut io: Io } {\n    %s\n}\n' % body)
                self.assertEqual(code, 'panic: ' + msg)

    def test_slices(self):
        out, code = self.both("""
fn sum { xs: []i32 } -> i32 {
    let mut t = 0
    let mut i: usize = 0
    while i < xs.len { t = t + xs[i]; i = i + 1 }
    return t
}
fn bump { xs: []mut i32 } {
    let mut i: usize = 0
    while i < xs.len { xs[i] = xs[i] + 1; i = i + 1 }
}
fn main { mut io: Io, args: Args } -> i32 {
    let mut a = [1, 2, 3, 4]
    bump{ xs = a[1..3] }
    io::println_i64{ &io, n = sum{ xs = &a } }
    let s = @slice(&a[0], 2)
    io::println_i64{ &io, n = s.ptr[1] + s[..1][0] }
    let mut e: []i32
    io::println_u64{ &io, n = e.len + args.len + args[0].len }
    return a[2]
}
""", args=['xyz'])
        self.assertEqual((out, code), ('12\n4\n4\n', 4))

    def test_matches_and_optionals(self):
        out, code = self.both("""
union Shape { circle{ r: f64 }, square{ side: f64 }, none }
fn area { s: *mut Shape } -> f64 {
    return match s {
        circle{ &r } => { r = r * 2.0; r }
        square{ side } => { side * side }
        else => { 0.0 }
    }
}
fn first { xs: []i32 } -> ?i32 {
    if xs.len == 0 { return null }
    return xs[0]
}
fn main { mut io: Io, args: Args } -> i32 {
    let mut c = Shape::circle{ r = 1.5 }
    io::println_f64{ &io, n = area{ s = &c } }
    io::println_f64{ &io, n = area{ s = &c } }
    let mut sq = Shape::square{ side = 3.0 }
    io::println_f64{ &io, n = area{ s = &sq } }
    let mut nums = [4, 5]
    let some{ value } = first{ xs = nums[..] } else { return 1 }
    let null = first{ xs = slice::empty(i32){} } else { return 2 }
    return value + @as(i32, args.len)
}
""", args=['x', 'y'])
        self.assertEqual((out, code), ('3.0\n6.0\n9.0\n', 6))


class ExternFns(Base):
    """`extern fn` and attributes (spec §18): C functions called through the C library, which
    every program links."""

    def assertExternError(self, src, msg, line, col):
        with self.assertRaises(CompileError) as cm:
            run(src)
        self.assertEqual((cm.exception.msg, cm.exception.pos[:2]), (msg, (line, col)), src)

    def test_calls(self):
        self.assertOutput("""
struct DivT { quot: i32, rem: i32 }

#c::symbol{ name = "labs" }
extern fn long_abs { n: i64 } -> i64
extern fn strlen { s: *u8 } -> usize
extern fn frexp { x: f64, mut exp: i32 } -> f64
extern fn div { numer: i32, denom: i32 } -> DivT

fn main { mut io: Io } {
    io::println_i64{ &io, n = long_abs{ n = -42 } }
    let s: []u8 = "hello\\0"
    io::println_u64{ &io, n = strlen{ s = s.ptr } }
    let mut e: i32 = 0
    io::println_f64{ &io, n = frexp{ x = 8.0, exp = &e } }
    io::println_i64{ &io, n = e }
    let d = div{ numer = 17, denom = 5 }
    io::println_i64{ &io, n = d.quot * 10 + d.rem }
}
""", "42\n5\n0.5\n4\n32\n")

    def test_capabilities_are_not_passed(self):
        # abs takes one int: the capability only says who may call it.
        self.assertOutput("""
extern fn abs { mut io: Io, n: i32 } -> i32
fn main { mut io: Io } {
    io::println_i64{ &io, n = abs{ &io, n = -7 } }
}
""", "7\n")

    def test_in_a_namespace_and_as_a_value(self):
        self.assertOutput("""
namespace cmath {
    #c::symbol{ name = "sqrt" }
    extern fn root { x: f64 } -> f64
}
fn apply { f: fn{ x: f64 } -> f64, x: f64 } -> f64 { return f{ x } }
fn main { mut io: Io } {
    io::println_f64{ &io, n = apply{ f = cmath::root, x = 16.0 } }
}
""", "4.0\n")

    def test_same_symbol_as_a_header(self):
        # The prototype has its own C name, so a signature that differs from string.h's doesn't
        # clash with it.
        self.assertOutput("""
extern fn memset { dst: *mut u8, value: i32, n: usize } -> *mut u8
fn main { mut io: Io } {
    let mut buf: [4]u8 = [0; 4]
    _ = memset{ dst = &buf[0], value = 7, n = 3 }
    io::println_i64{ &io, n = buf[0] + buf[2] + buf[3] }
}
""", "14\n")

    def test_ir(self):
        from toolchain import ir_sources
        text = ir_sources([("""
#c::symbol{ name = "labs" }
extern fn long_abs { n: i64 } -> i64
fn main {} -> i32 { return @trunc(i32, long_abs{ n = 3 }) }
""", None)])
        self.assertRegex(text, r'\(extern \d+ "long_abs" "labs" \[\("n" 0 \d+\)\] \d+\)')

    def test_syntax_errors(self):
        for src, msg, line, col in [
            ('extern fn f(T) { x: T }\nfn main {} {}', 'an extern fn cannot have generic parameters', 1, 12),
            ('extern fn f { x: i32 } {}\nfn main {} {}', 'an extern fn has no body: C provides it', 1, 24),
            ('extern f {}\nfn main {} {}', "expected 'fn', found 'f'", 1, 8),
            ('#5\nfn main {} {}', "expected a struct name after '#', found '5'", 1, 2),
            ('#a.b\nfn main {} {}', 'an attribute is a struct name or a struct literal', 1, 2),
            ('#S{ .. }\nfn main {} {}', 'an attribute is a struct name or a struct literal', 1, 2),
            ('#c::symbol{ name = "a" } fn f {} {}\nfn main {} {}',
             'an attribute goes on its own line, before a declaration', 1, 26),
            ('fn main {} {}\n#c::symbol{ name = "a" }\n', 'expected a declaration after an attribute, found end of file', 3, 1),
        ]:
            self.assertExternError(src, msg, line, col)

    def test_signature_errors(self):
        for src, msg, line, col in [
            ('extern fn f { x: ?i32 }\nfn main {} {}',
             "extern fn `f` can't pass `x` to C: it has type ?i32, which C has no equivalent of", 1, 15),
            ('extern fn f { g: fn{} }\nfn main {} {}',
             "extern fn `f` can't pass `g` to C: it has type fn{}, which C has no equivalent of", 1, 15),
            ('extern fn f { a: [4]u8 }\nfn main {} {}',
             "extern fn `f` can't pass `a` to C: it has type [4]u8, which C has no equivalent of", 1, 15),
            ('union U { a, b }\nextern fn f {} -> U\nfn main {} {}',
             "extern fn `f` can't return U: C has no equivalent of it", 2, 19),
        ]:
            self.assertExternError(src, msg, line, col)

    def test_attribute_errors(self):
        for src, msg, line, col in [
            ('#c::symbol{ name = "x" }\nfn f {} {}\nfn main {} {}', '`c::symbol` applies only to an extern fn', 1, 1),
            ('#c::symbol{ name = "1x" }\nextern fn f {}\nfn main {} {}', '`1x` is not a C identifier', 1, 1),
            ('#c::symbol{ name = "" }\nextern fn f {}\nfn main {} {}', '`` is not a C identifier', 1, 1),
            ('#c::symbol{ name = "a" }\n#c::symbol{ name = "b" }\nextern fn f {}\nfn main {} {}',
             'duplicate `c::symbol` attribute', 2, 1),
            ('#c::symbol\nextern fn f {}\nfn main {} {}', 'struct `symbol` is missing `name`', 1, 2),
            ('#c::symbol{ nme = "a" }\nextern fn f {}\nfn main {} {}', 'struct `symbol` has no field `nme`', 1, 13),
            ('union U { a{ x: i32 } }\n#U::a{ x = 1 }\nfn main {} {}', 'an attribute must be a struct literal', 2, 6),
            ('fn g {} -> i32 { return 1 }\nstruct S { x: i32 }\n#S{ x = g{} }\nfn main {} {}',
             'a const cannot call a function', 3, 10),
        ]:
            self.assertExternError(src, msg, line, col)

    def test_attributes_are_data(self):
        # Any struct can be an attribute, on any declaration; the compiler checks it and ignores
        # it.
        self.assertOutput("""
struct Tag {}
struct Rename { to: []u8, n: i32 }
const N: i32 = 3
namespace n {
    #Tag
    struct S { x: i32 }
}
#Rename{ to = "x", n = N + 1 }
#Tag
fn main { mut io: Io } {
    io::println_i64{ &io, n = 1 }
}
""", "1\n")


class NullablePointers(Base):
    """`?*T` is a plain pointer whose null is the address 0 (spec §8, Optional), so it has C's
    layout and crosses into C (§18)."""

    def test_layout(self):
        self.assertOutput("""
struct S { a: u8, p: ?*i32 }
fn main { mut io: Io } {
    io::println_u64{ &io, n = @size_of(?*i32) }
    io::println_u64{ &io, n = @align_of(?*mut i32) }
    io::println_u64{ &io, n = @size_of(S) }
    io::println_u64{ &io, n = @size_of(??*i32) }
    io::println_u64{ &io, n = @size_of(?[]u8) }
}
""", "8\n8\n16\n16\n24\n")

    def test_operations(self):
        self.assertOutput("""
struct Node { v: i32, next: ?*Node }
struct Holder { p: ?*i32 }
const EMPTY: Holder = Holder{ p = null }
const NOTHING: ?*i32 = null

fn first { n: ?*Node } -> i32 {
    let some{ value = p } = n else { return -1 }
    return p.v
}
fn describe { n: ?*Node } -> i32 {
    return match n {
        null          => { 0 }
        some{ value } => { value.v }
    }
}
fn pick { take: bool, p: *Node } -> ?*Node {
    if take { return p }
    return null
}
fn apply { f: fn{ n: ?*Node } -> i32, n: ?*Node } -> i32 { return f{ n } }

fn main { mut io: Io } {
    let a = Node{ v = 5, next = null }
    let b = Node{ v = 7, next = &a }
    io::println_i64{ &io, n = first{ n = &b } }
    io::println_i64{ &io, n = first{ n = null } }
    io::println_i64{ &io, n = describe{ n = b.next } }
    io::println_i64{ &io, n = describe{ n = a.next } }
    io::println_bool{ &io, n = pick{ take = false, p = &a } == null }
    let x = pick{ take = true, p = &b }
    if x != null { io::println_i64{ &io, n = x.v } }
    io::println_i64{ &io, n = apply{ f = describe, n = &a } }
    io::println_bool{ &io, n = EMPTY.p == null and NOTHING == null }

    // through a pointer: the binding is the place of the pointer itself
    let mut m: ?*Node = &a
    match &m {
        some{ &value } => { io::println_i64{ &io, n = value.*.v } }
        null           => {}
    }

    // an optional of a nullable pointer stays tagged around it
    let q: ??*Node = null
    io::println_bool{ &io, n = q == null }
}
""", "7\n-1\n5\n0\ntrue\n7\n5\ntrue\n5\ntrue\n")

    def test_extern_round_trip(self):
        self.assertOutput("""
extern fn strchr { s: *u8, c: i32 } -> ?*u8
extern fn strtol { s: *u8, end: ?*mut *u8, base: i32 } -> i64

fn main { mut io: Io } {
    let s: []u8 = "hello\\0"
    let hit = strchr{ s = s.ptr, c = 'l' }
    if hit != null { io::println_u64{ &io, n = @addr(hit) - @addr(s.ptr) } }
    io::println_bool{ &io, n = strchr{ s = s.ptr, c = 'z' } == null }
    let n: []u8 = "42xyz\\0"
    io::println_i64{ &io, n = strtol{ s = n.ptr, end = null, base = 10 } }
    let mut end: *u8 = n.ptr
    _ = strtol{ s = n.ptr, end = &end, base = 10 }
    io::println_u64{ &io, n = @addr(end) - @addr(n.ptr) }
}
""", "2\ntrue\n42\n2\n")

    def test_other_optionals_still_cannot_cross(self):
        with self.assertRaises(CompileError) as cm:
            run('extern fn f { s: ?[]u8 }\nfn main {} {}')
        self.assertIn("which C has no equivalent of", cm.exception.msg)


class Capabilities(Base):
    """`capability Name` (spec §15): permission that only `main` receives and passes down."""

    def assertCapError(self, src, msg, line, col):
        with self.assertRaises(CompileError) as cm:
            run(src)
        self.assertEqual((cm.exception.msg, cm.exception.pos[:2]), (msg, (line, col)), src)

    def test_declared_capability_gates_an_extern(self):
        self.assertOutput("""
namespace clib {
    // Permission to call the C library's math.
    capability Lib

    #c::symbol{ name = "labs" }
    extern fn long_abs { mut lib: Lib, n: i64 } -> i64
}

fn magnitude { mut lib: clib::Lib, n: i64 } -> i64 {
    return clib::long_abs{ &lib, n }
}

fn main { mut io: Io, mut lib: clib::Lib } {
    io::println_i64{ &io, n = magnitude{ &lib, n = -12 } }
}
""", "12\n")

    def test_std_capabilities_are_declarations(self):
        # Io is std's `capability Io`; a program's own declaration of the name shadows it.
        self.assertOutput("""
capability Io
fn main { mut io: Io, mut fs: Fs } -> i32 { return @as(i32, @size_of(Io)) + 3 }
""", "")

    def test_errors(self):
        for src, msg, line, col in [
            ('capability C\nfn main {} { let c = C{} }', '`C` is a capability: only `main` receives one, from the runtime', 2, 22),
            ('fn main {} { let x = Io{} }', '`Io` is a capability: only `main` receives one, from the runtime', 1, 22),
            ('capability C {}\nfn main {} {}', 'a capability without fields has no braces: write `capability Name`', 1, 14),
            ('capability C(T)\nfn main {} {}', 'a capability cannot have generic parameters', 1, 13),
            ('capability C\nstruct S { a: C(u8) }\nfn main {} {}', '`C` takes no type arguments', 2, 15),
            ('capability C\ncapability C\nfn main {} {}', '`C` is already declared in this scope', 2, 1),
            ('capability C\nfn main {} { let c: C\n    f{ c } }\nfn f { c: C } {}', '`c` may be read before it is assigned', 3, 8),
        ]:
            self.assertCapError(src, msg, line, col)

    def test_fields_are_c_functions(self):
        # A capability with fields holds C function pointers, which only its namespace's `load`
        # can set; holding one is the permission to call them, through it.
        self.assertOutput("""
namespace clib {
    capability Loader

    #c::symbol{ name = "llabs" }
    extern fn long_abs { n: i64 } -> i64
    #c::symbol{ name = "strlen" }
    extern fn str_len { s: c::String } -> usize

    capability Math {
        abs: extern fn{ n: i64 } -> i64,
        len: extern fn{ s: c::String } -> usize,
    }

    fn load { mut loader: Loader } -> ?Math {
        return Math{ abs = long_abs, len = str_len }
    }
}

fn twice { mut m: clib::Math, n: i64 } -> i64 { return m.abs{ n } * 2 }
fn through { p: *mut clib::Math } -> i64 { return p.abs{ n = -3 } }

fn main { mut io: Io, mut loader: clib::Loader } -> i32 {
    let some{ value = loaded } = clib::load{ &loader } else { return 1 }
    let mut m = loaded
    io::println_i64{ &io, n = m.abs{ n = -12 } }
    io::println_i64{ &io, n = twice{ &m, n = -5 } }
    io::println_i64{ &io, n = through{ p = &m } }
    io::println_u64{ &io, n = m.len{ s = "hello" } }
    io::println_u64{ &io, n = @size_of(clib::Math) }
    return 0
}
""", "12\n10\n3\n5\n16\n")

    def test_field_ir(self):
        from toolchain import ir_sources
        text = ir_sources([(CAP_FIELDS + 'fn main { mut l: m::L } -> i32 { let mut x = m::load{ &l }\n    return @trunc(i32, x.f{ n = -2 }) }', None)])
        self.assertIn('(cap "m::L"))', text)
        self.assertRegex(text, r'\(cap "m::M" 8 8 \[\("f" \d+ 0\)\]\)')

    def test_field_errors(self):
        callback_type = 'type T = extern fn{ mut x: m::M, n: i32 }\n#c::callback\nfn cb { n: i32 } {}\nextern fn take { f: T }\nfn main {} { take{ f = cb } }'
        for src, msg, line, col in [
            ('capability C { x: i32 }\nfn main {} {}', "capability `C`'s field `x` must be a C function pointer, `extern fn{ ... }`, not i32", 1, 16),
            ('capability C { f: ?extern fn{} }\nfn main {} {}', "capability `C`'s field `f` must be a C function pointer, `extern fn{ ... }`, not ?extern fn{}", 1, 16),
            ('capability C { f: fn{} }\nfn main {} {}', "capability `C`'s field `f` must be a C function pointer, `extern fn{ ... }`, not fn{}", 1, 16),
            ('capability C { f: extern fn{}, f: extern fn{} }\nfn main {} {}', 'duplicate field `f`', 1, 32),
            # made only by a function of its namespace that holds a capability or a bound function
            (CAP_FIELDS + 'fn main { mut l: m::L } { let x = m::M{ f = m::abs } }', 'capability `M` can only be made by a function of namespace `m`, which declares it', 8, 38),
            ('namespace m {\n    capability M { f: extern fn{} }\n    extern fn g {}\n    fn load {} -> M { return M{ f = g } }\n}\nfn main {} {}',
             'capability `M` can only be made by a function that holds a capability or a bound function: `load` takes neither', 4, 30),
            # a plain fn can't hold a capability: whoever calls it supplies its context
            ('namespace m {\n    capability M { f: extern fn{} }\n    extern fn g {}\n    fn load { find: fn{} -> ?extern fn{} } -> M { return M{ f = g } }\n}\nfn main {} {}',
             'capability `M` can only be made by a function that holds a capability or a bound function: `load` takes neither', 4, 58),
            ('namespace m {\n    capability M { f: extern fn{} }\n    extern fn g {}\n    const X: M = M{ f = g }\n}\nfn main {} {}',
             'capability `M` can only be made by a function of namespace `m`, which declares it', 4, 18),
            ('capability M { f: extern fn{} }\nextern fn g {}\nnamespace q { fn make { mut io: Io } -> M { return M{ f = g } } }\nfn main {} {}',
             'capability `M` can only be made by a function at the top level, which declares it', 3, 52),
            ('namespace m {\n    capability M { f: extern fn{}, g: extern fn{} }\n    extern fn h {}\n    fn load { mut io: Io } -> M { return M{ f = h } }\n}\nfn main {} {}',
             'capability `M` is missing `g`', 4, 43),
            # its fields can only be called, through a mutable one
            (CAP_FIELDS + 'fn main { mut l: m::L } { let mut x = m::load{ &l }\n    let f = x.f }', '`f` is a field of capability M: it can only be called, as `x.f{ ... }`', 9, 14),
            (CAP_FIELDS + 'fn g { f: extern fn{ n: i64 } -> i64 } {}\nfn main { mut l: m::L } { let mut x = m::load{ &l }\n    g{ f = x.f } }', '`f` is a field of capability M: it can only be called, as `x.f{ ... }`', 10, 13),
            (CAP_FIELDS + 'fn main { mut l: m::L } -> i32 { let mut x = m::load{ &l }\n    if x.f == m::abs { return 1 }\n    return 0 }', '`f` is a field of capability M: it can only be called, as `x.f{ ... }`', 9, 9),
            (CAP_FIELDS + 'fn main { mut l: m::L } { let mut x = m::load{ &l }\n    let p = @cast(*u8, x.f) }', '`f` is a field of capability M: it can only be called, as `x.f{ ... }`', 9, 25),
            (CAP_FIELDS + 'fn main { mut l: m::L } { let mut x = m::load{ &l }\n    x.f = m::abs }', '`f` is a field of capability M: it can only be called, as `x.f{ ... }`', 9, 6),
            (CAP_FIELDS + 'fn main { mut l: m::L } -> i32 { let x = m::load{ &l }\n    return @trunc(i32, x.f{ n = 1 }) }', '`x` is not a mutable place', 9, 24),
            (CAP_FIELDS + 'fn g { x: m::M } -> i64 { return x.f{ n = 1 } }\nfn main {} {}', '`x` is not a mutable place', 8, 34),
            (CAP_FIELDS + 'fn g { p: *m::M } -> i64 { return p.f{ n = -3 } }\nfn main {} {}', 'cannot write through *M; it needs to be a `*mut`', 8, 36),
            # neither the runtime nor a callback's thunk can supply one
            (CAP_FIELDS + 'fn main { mut x: m::M } {}', '`main` cannot take `M`: a capability with fields comes from a function of its namespace, not the runtime', 8, 1),
            (CAP_FIELDS + '#c::callback\nfn cb { mut x: m::M, n: i32 } {}\nfn main {} {}',
             "callback `cb` can't take `x`: capability M has fields, and nothing can supply one when C calls the callback", 9, 1),
            (CAP_FIELDS + callback_type,
             "callback `cb` can't have type extern fn{ mut x: M, n: i32 }: its field `x` is capability M, which has fields, and nothing can supply one when C calls the callback", 12, 24),
        ]:
            self.assertCapError(src, msg, line, col)

    def test_made_through_a_bound_function(self):
        # A bound function may hold a capability (spec §1.3), so a load that takes only a lookup
        # can make one and names no library: here the lookup is lib's, bound to its capability.
        self.assertOutput("""
namespace lib {
    capability Lib
    #c::symbol{ name = "llabs" }
    extern fn long_abs { n: i64 } -> i64
    fn find { mut l: Lib, name: c::String } -> ?extern fn{ n: i64 } -> i64 { return long_abs }
}

namespace m {
    capability M { f: extern fn{ n: i64 } -> i64 }
    fn load { find: &fn{ name: c::String } -> ?extern fn{ n: i64 } -> i64 } -> ?M {
        let some{ value = f } = find{ name = "llabs" } else { return null }
        return M{ f }
    }
}

fn main { mut io: Io, mut l: lib::Lib } -> i32 {
    let some{ value = loaded } = m::load{ find = lib::find{ &l, _ } } else { return 1 }
    let mut x = loaded
    io::println_i64{ &io, n = x.f{ n = -9 } }
    return 0
}
""", "9\n")

    def test_extern_takes_one(self):
        # An extern fn may take one: like any capability, it isn't passed to C.
        self.assertOutput(CAP_FIELDS + """
#c::symbol{ name = "llabs" }
extern fn magnitude { mut x: m::M, n: i64 } -> i64
fn main { mut io: Io, mut l: m::L } {
    let mut x = m::load{ &l }
    io::println_i64{ &io, n = magnitude{ &x, n = -7 } + x.f{ n = -1 } }
}
""", "8\n")

    def test_inclusion(self):
        # `..A` gives a capability A's fields where it stands (spec §15), and it converts to A:
        # a `mut` field takes a pointer to it, as is when A's fields come first (B's `..A`) and
        # as a copy when they don't (C's), and a value converts too. A literal of one made in
        # its namespace may spread one it includes.
        self.assertOutput(CAP_CHAIN + """
fn mag { mut a: m::A, n: i64 } -> i64 { return a.abs{ n } }
fn size { mut b: m::B, s: c::String } -> usize { return b.len{ s } }
fn via { p: *mut m::C } -> i64 { return mag{ a = p, n = -8 } }
fn fwd { mut a: m::C, n: i64 } -> i64 { return mag{ .. } }
fn first { a: m::A } -> ?m::A { return a }

fn main { mut io: Io, mut l: m::L } -> i32 {
    let mut b = m::load_b{ &l }
    let mut c = m::load_c{ &l }
    io::println_i64{ &io, n = b.abs{ n = -1 } + c.abs{ n = -2 } }
    io::println_u64{ &io, n = b.len{ s = "four" } + c.len{ s = "five!" } }
    io::println_i64{ &io, n = @as(i64, c.int{ s = "42" }) }
    io::println_i64{ &io, n = mag{ a = &b, n = -3 } }
    io::println_i64{ &io, n = mag{ a = &c, n = -4 } }
    io::println_u64{ &io, n = size{ b = &c, s = "seven!!" } }
    io::println_i64{ &io, n = via{ p = &c } }
    io::println_i64{ &io, n = fwd{ a = &c, n = -9 } }
    let mut a: m::A = c
    let mut a2 = first{ a = b } ifnull { return 1 }
    io::println_i64{ &io, n = a.abs{ n = -5 } + a2.abs{ n = -6 } }
    io::println_u64{ &io, n = @size_of(m::B) + @size_of(m::C) }
    return 0
}
""", "3\n9\n42\n3\n4\n7\n8\n9\n11\n40\n")

    def test_inclusion_ir(self):
        # A pointer to a B is one to an A; to pass a C as an A, its function is copied into a
        # local, `with` sets it, and its address is passed.
        from toolchain import ir_sources
        text = ir_sources([(CAP_CHAIN + """
fn mag { mut a: m::A } -> i64 { return a.abs{ n = -1 } }
fn main { mut l: m::L } -> i32 {
    let mut b = m::load_b{ &l }
    let mut c = m::load_c{ &l }
    return @trunc(i32, mag{ a = &b } + mag{ a = &c })
}""", None)])
        self.assertRegex(text, r'\(cap "m::C" 24 8 \[\("int" \d+ 0\) \("abs" \d+ 8\) \("len" \d+ 16\)\]\)')
        self.assertRegex(text, r'\(0 \(cast \d+ \(addr \d+ \(local \d+ 1\)\)\)\)')
        self.assertRegex(text, r'\(0 \(with \d+ 3 \(struct \d+ \[\(0 \(field \d+ \(deref \d+ \(addr \d+ \(local \d+ 2\)\) [^)]*\) 1\)\)\]\) \(addr \d+ \(local \d+ 3\)\)\)\)')

    def test_inclusion_errors(self):
        for src, msg, line, col in [
            # a field reaches a capability once
            (CAP_CHAIN + 'capability X { ..m::A, abs: extern fn{ n: i64 } -> i64 }\nfn main {} {}',
             'capability `X` declares `abs`, which it includes from `A`', 16, 24),
            (CAP_CHAIN + 'capability X { abs: extern fn{ n: i64 } -> i64, ..m::A }\nfn main {} {}',
             'capability `X` declares `abs`, which it includes from `A`', 16, 49),
            (CAP_CHAIN + 'capability Y { abs: extern fn{ n: i64 } -> i64 }\ncapability X { ..m::A, ..Y }\nfn main {} {}',
             'capability `X` includes `abs` twice: from `A` and from `Y`', 17, 24),
            (CAP_CHAIN + 'capability X { ..m::B, ..m::A }\nfn main {} {}', 'capability `X` includes `abs` twice: from `B` and from `A`', 16, 24),
            # no cycles
            ('capability P { ..P }\nfn main {} {}', 'capability `P` includes itself', 1, 16),
            ('capability P { ..Q, f: extern fn{} }\ncapability Q { ..P }\nfn main {} {}', 'capability `P` includes itself, through `Q`', 2, 16),
            # only a capability, and in one with fields only one with fields
            ('capability L\ncapability X { f: extern fn{}, ..L }\nfn main {} {}', "capability `X` can't include `L`: it has no fields", 2, 32),
            ('capability L\ncapability X { ..L, f: extern fn{} }\nfn main {} {}', "capability `X` can't include `L`: it has no fields", 2, 16),
            (CAP_CHAIN + 'capability L\ncapability X { ..m::A, ..L }\nfn main {} {}', "capability `X` can't include `L`: it has no fields", 17, 24),
            ('capability V { extern opterr: i32 }\ncapability X { f: extern fn{}, ..V }\nfn main {} {}', "capability `X` can't include `V`: it has only C variables", 2, 32),
            ('struct S { a: i32 }\ncapability X { ..S }\nfn main {} {}', 'capability `X` can only include a capability, not S', 2, 16),
            # it converts only to what it includes
            (CAP_CHAIN + 'fn need { mut b: m::B } {}\nfn main { mut l: m::L } { let mut a = m::load_a{ &l }\n    need{ b = &a } }', 'expected *mut B, got *mut A', 18, 15),
            (CAP_CHAIN + 'fn main { mut l: m::L } { let a = m::load_a{ &l }\n    let b: m::B = a }', 'expected B, got A', 17, 19),
            (CAP_CHAIN + 'fn main { mut l: m::L } { let mut a = m::load_a{ &l }\n    let p: *mut m::A = &a\n    let q: *mut m::B = p }', 'expected *mut B, got *mut A', 18, 24),
            # a spread is only where a literal may be, of one the literal's capability includes,
            # and supplies its fields once
            (CAP_CHAIN + 'fn main { mut l: m::L } { let a = m::load_a{ &l }\n    let b = m::B{ ..a, len = m::len } }',
             'capability `B` can only be made by a function of namespace `m`, which declares it', 17, 16),
            (CAP_CHAIN.replace('    fn load_b', '    fn bad { mut l: L } -> B { return B{ ..load_b{ &l }, len } }\n    fn load_b') + 'fn main {} {}',
             "`..load_b{ &l }` has type B, which capability `B` doesn't include", 13, 50),
            (CAP_CHAIN.replace('    fn load_b', '    fn bad { mut l: L } -> B { return B{ ..load_a{ &l }, abs, len } }\n    fn load_b') + 'fn main {} {}',
             '`abs` is supplied more than once', 13, 42),
            (CAP_CHAIN.replace('    fn load_b', '    fn bad { mut l: L } -> B { return B{ ..load_a{ &l } } }\n    fn load_b') + 'fn main {} {}',
             'capability `B` is missing `len`', 13, 40),
            (CAP_CHAIN + 'fn f { a: m::A } {}\nfn main { mut l: m::L } { let a = m::load_a{ &l }\n    f{ ..a } }', "`..a` is allowed only in a capability's literal", 18, 8),
            ('struct S { a: i32 }\nfn main {} { let s = S{ a = 1 }\n    let t = S{ ..s } }', "`..s` is allowed only in a capability's literal", 3, 16),
            # one is never replaced, whole or inside another value: a `mut` field may hold a copy
            (CAP_CHAIN + 'fn set { mut a: m::A, b: m::A } { a = b }\nfn main {} {}',
             'cannot assign A, which is a capability with fields: one is never replaced, only declared with its value or assigned once to a `let x: T`', 16, 35),
            (CAP_CHAIN + 'fn main { mut l: m::L } { let mut c = m::load_c{ &l }\n    c = m::load_c{ &l } }',
             'cannot assign C, which is a capability with fields: one is never replaced, only declared with its value or assigned once to a `let x: T`', 17, 5),
            (CAP_CHAIN + 'struct H { c: m::C, n: i32 }\nfn bump { mut h: H } { h = h }\nfn main {} {}',
             'cannot assign H, which holds a capability with fields: one is never replaced, only declared with its value or assigned once to a `let x: T`', 17, 24),
            (CAP_CHAIN + 'fn main { mut l: m::L } { let mut o: ?m::A = null\n    o = m::load_a{ &l } }',
             'cannot assign ?A, which holds a capability with fields: one is never replaced, only declared with its value or assigned once to a `let x: T`', 17, 5),
        ]:
            self.assertCapError(src, msg, line, col)

    def test_capability_assigned_once(self):
        # A `let x: T` of a capability is assigned once, and a value holding one may still have
        # its other fields assigned (spec §15, rule 8).
        self.assertOutput(CAP_CHAIN + """
struct H { c: m::C, n: i64 }
fn main { mut io: Io, mut l: m::L } -> i32 {
    let a: m::A
    if true { a = m::load_a{ &l } } else { a = m::load_c{ &l } }
    let mut h = H{ c = m::load_c{ &l }, n = -1 }
    h.n = h.n - 1
    let mut b = a
    io::println_i64{ &io, n = b.abs{ n = h.n } }
    return 0
}
""", "2\n")

    def test_c_variables(self):
        # `extern name: T` in a capability is the C variable `name` (spec §15): getopt's here,
        # which every libc has. A function of the namespace that declares it reads it through
        # the capability, or a pointer to one; it takes no space, so a capability with only
        # variables is one `main` receives. One without fields may be included by one that has
        # none either, and converts to it, so another namespace can hold a platform's.
        # `#c::symbol` names a variable's symbol, as an extern fn's, through inclusions too.
        self.assertOutput("""
namespace getopt {
    capability Opts {
        #c::symbol{ name = "opterr" }
        extern reports: i32,
        extern optind: i32,
    }
    fn errors_on { mut o: Opts } -> bool { return o.reports != 0 }
    fn index { p: *Opts } -> i32 { return p.optind }
}

namespace m {
    capability L
    #c::symbol{ name = "llabs" }
    extern fn abs { n: i64 } -> i64
    capability M { f: extern fn{ n: i64 } -> i64, extern optind: i32 }
    fn load { mut l: L } -> M { return M{ f = abs } }
    fn next { mut x: M } -> i64 { return x.f{ n = -10 } + @as(i64, x.optind) }
}

capability Bare
capability Mine { ..getopt::Opts, ..Bare }

fn bare { mut b: Bare } -> i32 { return 3 }

fn main { mut io: Io, mut o: getopt::Opts, mut mine: Mine, mut l: m::L } -> i32 {
    io::println_bool{ &io, n = getopt::errors_on{ &o } }
    io::println_i64{ &io, n = getopt::index{ p = &o } }
    io::println_bool{ &io, n = getopt::errors_on{ o = &mine } }
    io::println_i64{ &io, n = bare{ b = &mine } }
    let mut x = m::load{ &l }
    io::println_i64{ &io, n = m::next{ &x } }
    io::println_u64{ &io, n = @size_of(getopt::Opts) + @size_of(Mine) + @size_of(m::M) }
    return 0
}
""", "true\n1\ntrue\n3\n11\n8\n")

    def test_c_variable_ir(self):
        # A variable is an item, declared once however many capabilities read it, and a read is
        # its value.
        from toolchain import ir_sources
        text = ir_sources([("""
namespace g {
    capability O { extern optind: i32 }
    fn a { mut o: O } -> i32 { return o.optind }
    fn b { p: *O } -> i32 { return p.optind }
}
fn main { mut o: g::O } -> i32 { return g::a{ &o } + g::b{ p = &o } }
""", None)])
        self.assertRegex(text, r'\(var 0 "optind" "optind" \d+\)')
        self.assertNotIn('(var 1', text)
        self.assertEqual(text.count('(cvar '), 2)
        text = ir_sources([('capability O {\n    #c::symbol{ name = "opterr" }\n    extern reports: i32\n}\nfn main { mut o: O } -> i32 { return o.reports }', None)])
        self.assertRegex(text, r'\(var 0 "reports" "opterr" \d+\)')

    def test_c_variable_errors(self):
        for src, msg, line, col in [
            # read only by a function of the namespace that declares the capability
            ('namespace g { capability O { extern opterr: i32 } }\nfn main { mut o: g::O } -> i32 { return o.opterr }',
             '`opterr` is a C variable of capability `O`: only a function of namespace `g`, which declares it, can read it', 2, 42),
            ('capability O { extern opterr: i32 }\nnamespace q { fn f { mut o: O } -> i32 { return o.opterr } }\nfn main {} {}',
             '`opterr` is a C variable of capability `O`: only a function at the top level, which declares it, can read it', 2, 50),
            ('namespace g { capability O { extern opterr: i32 } }\ncapability X { ..g::O }\nfn main { mut x: X } -> i32 { return x.opterr }',
             '`opterr` is a C variable of capability `O`: only a function of namespace `g`, which declares it, can read it', 3, 39),
            # its value, not a place
            ('capability O { extern opterr: i32 }\nfn main { mut o: O } { o.opterr = 1 }', '`.opterr` is not a place', 2, 25),
            ('capability O { extern opterr: i32 }\nfn main { mut o: O } { let p = &o.opterr }', '`.opterr` is not a place', 2, 34),
            # of a type C stores
            ('capability O { extern x: []u8 }\nfn main {} {}', "capability `O`'s C variable `x` can't have type []u8: C has no equivalent of it", 1, 16),
            ('capability O { extern x: Io }\nfn main {} {}', "capability `O`'s C variable `x` can't have type Io: C has no equivalent of it", 1, 16),
            ('capability O { extern x: fn{} }\nfn main {} {}', "capability `O`'s C variable `x` can't have type fn{}: C has no equivalent of it", 1, 16),
            # one name, once
            ('capability O { extern x: i32, x: extern fn{} }\nfn main {} {}', 'duplicate field `x`', 1, 31),
            ('capability O { extern x: i32, extern x: i32 }\nfn main {} {}', 'duplicate field `x`', 1, 31),
            ('capability V { extern x: i32 }\ncapability O { ..V, extern x: i32 }\nfn main {} {}', 'capability `O` declares `x`, which it includes from `V`', 2, 21),
            ('capability V { extern x: i32 }\ncapability W { extern x: i32 }\ncapability O { ..V, ..W }\nfn main {} {}',
             'capability `O` includes `x` twice: from `V` and from `W`', 3, 21),
            # `extern` marks a capability's field only
            ('struct S { extern x: i32 }\nfn main {} {}', "expected a name, found 'extern'", 1, 12),
            # `#c::symbol` names a C variable's symbol; a field's attributes go on lines before it
            ('capability O {\n    #c::symbol{ name = "x" }\n    f: extern fn{}\n}\nfn main {} {}',
             "`c::symbol` on a capability's field applies only to a C variable, `extern name: T`", 2, 5),
            ('capability O {\n    #c::symbol{ name = "x" }\n    #c::symbol{ name = "y" }\n    extern a: i32\n}\nfn main {} {}', 'duplicate `c::symbol` attribute', 3, 5),
            ('capability O {\n    #c::symbol{ name = "not ok" }\n    extern a: i32\n}\nfn main {} {}', '`not ok` is not a C identifier', 2, 5),
            ('capability O {\n    #c::callback\n    extern a: i32\n}\nfn main {} {}', '`c::callback` applies only to a fn', 2, 5),
            ('capability O {\n    #c::symbl{ name = "x" }\n    extern a: i32\n}\nfn main {} {}', '`symbl` not found in namespace `c`', 2, 9),
            ('capability O {\n    #c::symbol{ name = "x" } extern a: i32\n}\nfn main {} {}', 'an attribute goes on its own line, before a field', 2, 30),
            ('capability O {\n    #c::symbol{ name = "x" }\n    ..Io\n}\nfn main {} {}', "expected a field after an attribute, found '..'", 3, 5),
        ]:
            self.assertCapError(src, msg, line, col)


# A capability with fields, M, and the function of its namespace that makes one.
CAP_FIELDS = """namespace m {
    capability L
    capability M { f: extern fn{ n: i64 } -> i64 }
    #c::symbol{ name = "llabs" }
    extern fn abs { n: i64 } -> i64
    fn load { mut l: L } -> M { return M{ f = abs } }
}
"""


# Capabilities that include others: B includes A first, so an A's fields begin a B's, and C
# includes B after a field of its own.
CAP_CHAIN = """namespace m {
    capability L
    #c::symbol{ name = "llabs" }
    extern fn abs { n: i64 } -> i64
    #c::symbol{ name = "strlen" }
    extern fn len { s: c::String } -> usize
    #c::symbol{ name = "atoi" }
    extern fn int { s: c::String } -> i32
    capability A { abs: extern fn{ n: i64 } -> i64 }
    capability B { ..A, len: extern fn{ s: c::String } -> usize }
    capability C { int: extern fn{ s: c::String } -> i32, ..B }
    fn load_a { mut l: L } -> A { return A{ abs } }
    fn load_b { mut l: L } -> B { return B{ ..load_a{ &l }, len } }
    fn load_c { mut l: L } -> C { return C{ int, ..load_b{ &l } } }
}
"""


PROC_MAIN = """
fn main { mut io: Io, mut proc: Proc, args: Args } -> i32 {
    let mut mem: [65536]u8
    let mut heap = arena::new{ buf = mem[..] }
    let mut argv = list::new([]u8){ realloc = arena::alloc, &heap }
    let mut env = list::new([]u8){ realloc = arena::alloc, &heap }
%s
}
"""


class Proc(Base):
    """std's proc: running programs, and this one's environment. The programs run are the
    Python running the tests, so they exist on every platform."""

    def run_proc(self, body, args=()):
        out = io.StringIO()
        code = run_source(PROC_MAIN % body, out=out, args=list(args))
        return out.getvalue(), code

    def test_exit_code_and_env(self):
        script = 'import os, sys; print(os.environ["CTX_TEST_FOO"]); sys.exit(7)'
        out, code = self.run_proc("""
    _ = list::push{ list = &argv, item = args[0] } and list::push{ list = &argv, item = "-c" }
        and list::push{ list = &argv, item = args[1] }
    _ = list::push{ list = &env, item = "CTX_TEST_FOO=bar baz" }
    io::println{ &io, s = "before" }
    match proc::run{ &proc, argv = list::items{ list = argv }, env = list::items{ list = env } } {
        ok{ value }  => { io::println_i64{ &io, n = value } }
        err          => { return 1 }
    }
    return 0
""", [sys.executable, script])
        # The child's output comes after "before": proc::run flushes this program's first.
        self.assertEqual(out.replace('\r\n', '\n'), 'before\nbar baz\n7\n')
        self.assertEqual(code, 0)

    def test_missing_program(self):
        out, code = self.run_proc("""
    _ = list::push{ list = &argv, item = "ctx-no-such-program-anywhere" }
    match proc::run{ &proc, argv = list::items{ list = argv }, env = slice::empty([]u8){} } {
        ok              => { return 1 }
        proc::not_found => { return 0 }
        else            => { return 2 }
    }
""")
        self.assertEqual(code, 0)

    def test_env_and_exe_path(self):
        os.environ['CTX_TEST_ENV'] = 'set'
        self.addCleanup(os.environ.pop, 'CTX_TEST_ENV', None)
        out, code = self.run_proc("""
    let v = proc::env{ &proc, name = "CTX_TEST_ENV" }
    if v != null { io::println{ &io, s = utf8::of{ chars = v } } }
    io::println_bool{ &io, n = proc::env{ &proc, name = "CTX_TEST_UNSET_VAR" } == null }
    io::println_bool{ &io, n = proc::exe_path{ &proc }.len > 0 }
    return 0
""")
        self.assertEqual((out, code), ('set\ntrue\ntrue\n', 0))

    def test_bad_env_entry_panics(self):
        with self.assertRaises(Panic) as cm:
            self.run_proc("""
    _ = list::push{ list = &argv, item = "x" }
    _ = list::push{ list = &env, item = "NOEQUALS" }
    _ = proc::run{ &proc, argv = list::items{ list = argv }, env = list::items{ list = env } }
    return 0
""")
        self.assertIn('an environment entry is KEY=VALUE', cm.exception.msg)


class CtxcDriver(Base):
    """`ctxc run` and `ctxc exe` (ctxc/drive.ctx): ctxc and a C compiler, without Python."""

    def project(self, files):
        import tempfile
        d = tempfile.mkdtemp(prefix='ctxdrive-', dir=os.path.join(ROOT, 'build'))
        self.addCleanup(shutil.rmtree, d, True)
        for name, text in files.items():
            path = os.path.join(d, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(text)
        return d

    def ctxc(self, *args):
        import subprocess
        from toolchain import native_ctxc
        env = dict(os.environ, CTX_HOME=ROOT)
        r = subprocess.run([native_ctxc(), *args], capture_output=True, env=env)
        return r.returncode, r.stdout.decode().replace('\r\n', '\n'), r.stderr.decode()

    def test_run_a_file_with_arguments(self):
        d = self.project({'hello.ctx': """
fn main { mut io: Io, args: Args } -> i32 {
    io::println{ &io, s = utf8::of{ chars = args[0] } }
    return 3
}
"""})
        self.assertEqual(self.ctxc('run', os.path.join(d, 'hello.ctx'), '--', 'hi')[:2], (3, 'hi\n'))

    def test_run_a_build_program(self):
        d = self.project({
            'build.ctx': """
fn build { mut b: Build } {
    _ = build::exe{ &b, name = "first", root = "app" }
    _ = build::exe{ &b, name = "second", root = "." }
}
""",
            'app/main.ctx': 'fn main { mut io: Io } { io::println{ &io, s = "from app" } }\n',
            'main.ctx': 'fn main { mut io: Io } { io::println{ &io, s = "from top" } }\n',
        })
        self.assertEqual(self.ctxc('run', d)[:2], (0, 'from app\n'))
        out = os.path.join(d, 'prog')
        self.assertEqual(self.ctxc('exe', d, '-o', out)[0], 0)
        from toolchain import run_exe
        got = io.StringIO()
        run_exe(out, out=got)
        self.assertEqual(got.getvalue(), 'from app\n')

    def test_errors(self):
        d = self.project({'bad.ctx': 'fn main {} { let x: i32 = true }\n'})
        code, _, err = self.ctxc('run', os.path.join(d, 'bad.ctx'))
        self.assertEqual(code, 1)
        self.assertIn('bad.ctx:1:27: error: expected i32, got bool', err)
        code, _, err = self.ctxc('run', os.path.join(d, 'missing.ctx'))
        self.assertEqual(code, 1)
        self.assertIn('missing.ctx: cannot read', err)
        self.assertEqual(self.ctxc('run')[0], 2)


class BuildPrograms(Base):
    """Build programs (spec §19): a directory's build.ctx, through toolchain.build_project."""

    def project(self, files):
        import tempfile
        d = tempfile.mkdtemp(prefix='ctxproj-', dir=os.path.join(ROOT, 'build'))
        self.addCleanup(shutil.rmtree, d, True)
        for name, text in files.items():
            path = os.path.join(d, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(text)
        return d

    def run_exe(self, exe):
        from toolchain import run_exe
        out = io.StringIO()
        run_exe(exe, out=out)
        return out.getvalue()

    def test_links_a_static_library(self):
        import subprocess
        from toolchain import build_project, compiler
        if shutil.which('ar') is None:
            self.skipTest('no ar')
        d = self.project({
            'lib/add.c': 'int ctxtest_add(int a, int b) { return a + b; }\n',
            'build.ctx': """
fn build { mut b: Build } {
    let exe = build::exe{ &b, name = "adder", root = "src" }
    build::lib_path{ &b, exe, path = "lib" }
    build::link{ &b, exe, lib = "ctxtest" }
}
""",
            'src/main.ctx': """
namespace ctxtest {
    capability Lib
    extern fn ctxtest_add { mut lib: Lib, a: i32, b: i32 } -> i32
}
fn main { mut io: Io, mut lib: ctxtest::Lib } {
    io::println_i64{ &io, n = ctxtest::ctxtest_add{ &lib, a = 40, b = 2 } }
}
""",
        })
        cc, env = compiler()
        lib = os.path.join(d, 'lib')
        subprocess.run(cc + ['-c', os.path.join(lib, 'add.c'), '-o', os.path.join(lib, 'add.o')], check=True, env=env)
        subprocess.run(['ar', 'rcs', os.path.join(lib, 'libctxtest.a'), os.path.join(lib, 'add.o')], check=True)
        [(name, exe)] = build_project(d)
        self.assertEqual(name, 'adder')
        self.assertEqual(self.run_exe(exe), '42\n')

    def test_choices_by_os_and_several_executables(self):
        from toolchain import build_project
        d = self.project({
            'build.ctx': """
fn build { mut b: Build } {
    let os: []u8 = match build::os{ &b } {
        windows => { "windows" }
        macos   => { "macos" }
        linux   => { "linux" }
    }
    _ = build::exe{ &b, name = os, root = "one" }
    _ = build::exe{ &b, name = "two", root = "." }
}
""",
            'one/main.ctx': 'fn main { mut io: Io } { io::println{ &io, s = "one" } }\n',
            'main.ctx': 'fn main { mut io: Io } { io::println{ &io, s = "two" } }\n',
        })
        built = build_project(d)
        host = 'windows' if os.name == 'nt' else 'macos' if sys.platform == 'darwin' else 'linux'
        self.assertEqual([name for name, _ in built], [host, 'two'])
        # The top directory's .ctx files are an executable's, but build.ctx never is.
        self.assertEqual([self.run_exe(exe) for _, exe in built], ['one\n', 'two\n'])

    def test_graph_without_the_driver(self):
        # Run directly, a build program prints its records.
        self.assertOutput("""
fn build { mut b: Build } {
    let exe = build::exe{ &b, name = "demo", root = "src" }
    build::link{ &b, exe, lib = "m" }
    build::framework{ &b, exe, name = "Cocoa" }
    build::lib_path{ &b, exe, path = "/opt/lib" }
}
""", "exe\t0\tdemo\tsrc\nlink\t0\tm\nframework\t0\tCocoa\nlibpath\t0\t/opt/lib\n")

    def test_errors(self):
        from toolchain import build_project
        d = self.project({'build.ctx': 'fn build { mut b: Build } {\n    build::link{ &b, lib = "m" }\n}\n'})
        with self.assertRaises(CompileError) as cm:
            build_project(d)
        self.assertEqual((cm.exception.msg, cm.exception.pos), ('call to `build::link` is missing `exe`', (2, 16, 'build.ctx')))
        d = self.project({'build.ctx': 'fn build { mut b: Build } {\n    _ = build::exe{ &b, name = "", root = "." }\n}\n'})
        with self.assertRaises(Panic) as cm:
            build_project(d)
        self.assertEqual(cm.exception.msg, 'build: empty name')
        d = self.project({'build.ctx': 'fn build { mut b: Build } {\n    _ = build::exe{ &b, name = "x", root = "nothing" }\n}\n'})
        with self.assertRaises(CompileError) as cm:
            build_project(d)
        self.assertEqual((cm.exception.msg, cm.exception.pos), ('no .ctx files in directory', (0, 0, 'nothing')))
        self.assertPanic('fn build { mut b: Build } { build::link{ &b, exe = build::Exe{ id = 3 }, lib = "m" } }',
                         'build: no executable 3')

    def test_entry_errors(self):
        self.assertCompileError('fn main { mut b: Build } {}',
                                "`main` cannot take a Build: only a build program's `fn build` receives one")
        self.assertCompileError('fn build { n: i32 } {}',
                                '`build` context field `n` must have a capability type or be `args: Args`, got i32')
        self.assertCompileError('fn build {} -> u8 { return 1 }', '`build` can only return i32 (the exit code), not u8')
        # With a `main`, `build` is an ordinary function.
        self.assertOutput('fn build {} -> i32 { return 7 }\nfn main { mut io: Io } { io::println_i64{ &io, n = build{} } }', '7\n')


class CLib(Base):
    """A program over a small C library: LIB_C as libctxtest.a, HEAD before each main."""

    BUILD = """
fn build { mut b: Build } {
    let exe = build::exe{ &b, name = "cfn", root = "src" }
    build::lib_path{ &b, exe, path = "lib" }
    build::link{ &b, exe, lib = "ctxtest" }
}
"""

    def run_with_lib(self, main):
        import subprocess
        import tempfile
        from toolchain import build_project, compiler, run_exe
        if shutil.which('ar') is None:
            self.skipTest('no ar')
        d = tempfile.mkdtemp(prefix='ctxcfn-', dir=os.path.join(ROOT, 'build'))
        self.addCleanup(shutil.rmtree, d, True)
        for name, text in [('lib/op.c', self.LIB_C), ('build.ctx', self.BUILD), ('src/main.ctx', self.HEAD + main)]:
            path = os.path.join(d, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(text)
        cc, env = compiler()
        lib = os.path.join(d, 'lib')
        subprocess.run(cc + ['-c', os.path.join(lib, 'op.c'), '-o', os.path.join(lib, 'op.o')], check=True, env=env)
        subprocess.run(['ar', 'rcs', os.path.join(lib, 'libctxtest.a'), os.path.join(lib, 'op.o')], check=True)
        [(_, exe)] = build_project(d)
        out = io.StringIO()
        run_exe(exe, out=out)
        return out.getvalue()

    def assertCfnError(self, src, msg, line, col):
        with self.assertRaises(CompileError) as cm:
            run(src)
        self.assertEqual((cm.exception.msg, cm.exception.pos[:2]), (msg, (line, col)), src)


class CFunctionPointers(CLib):
    """`extern fn{...} -> R`, a C function pointer (spec §12, §18): from an address with @cast,
    from a named extern fn, called with its fields in C's order."""

    LIB_C = """
#include <stdint.h>
static int32_t add(int32_t a, int32_t b) { return a + b; }
static int32_t mul(int32_t a, int32_t b) { return a * b; }
void *ctxtest_op(int32_t which) { return which == 0 ? (void *)add : which == 1 ? (void *)mul : (void *)0; }
int32_t (*ctxtest_op_typed(int32_t which))(int32_t, int32_t) { return which == 0 ? add : which == 1 ? mul : 0; }
int32_t ctxtest_apply(int32_t (*f)(int32_t, int32_t), int32_t a, int32_t b) { return f(a, b); }
int32_t ctxtest_sub(int32_t a, int32_t b) { return a - b; }
void ctxtest_out(int32_t (*f)(int32_t, int32_t), int32_t *out) { *out = f(20, 22); }
"""

    HEAD = """
type Op = extern fn{ a: i32, b: i32 } -> i32
extern fn ctxtest_op { which: i32 } -> ?*u8
extern fn ctxtest_op_typed { which: i32 } -> ?Op
extern fn ctxtest_apply { f: Op, a: i32, b: i32 } -> i32
extern fn ctxtest_sub { a: i32, b: i32 } -> i32
extern fn ctxtest_out { f: Op, mut out: i32 }
"""

    def test_from_an_address_and_in_a_struct(self):
        self.assertEqual(self.run_with_lib("""
capability Lib
struct Ops { add: Op, gated: extern fn{ mut lib: Lib, a: i32, b: i32 } -> i32 }
fn main { mut io: Io, mut lib: Lib } {
    let some{ value = p } = ctxtest_op{ which = 0 } else { return }
    let add = @cast(Op, p)
    io::println_i64{ &io, n = add{ a = 2, b = 3 } }
    // Fields go to C in declaration order, whatever order they are written in.
    let ops = Ops{ add, gated = @cast(extern fn{ mut lib: Lib, a: i32, b: i32 } -> i32, p) }
    io::println_i64{ &io, n = ops.add{ b = 10, a = 4 } }
    io::println_i64{ &io, n = ops.gated{ &lib, a = 1, b = 1 } }
    let back = @cast(*u8, add)
    io::println_bool{ &io, n = @addr(back) == @addr(p) }
}
"""), "5\n14\n2\ntrue\n")

    def test_nullable(self):
        self.assertEqual(self.run_with_lib("""
fn main { mut io: Io } {
    let m = ctxtest_op_typed{ which = 1 }
    if m != null { io::println_i64{ &io, n = m{ a = 6, b = 7 } } }
    let none = ctxtest_op_typed{ which = 5 }
    if none == null { io::println{ &io, s = "null" } }
    let some{ value = add } = ctxtest_op_typed{ which = 0 } else { return }
    io::println_i64{ &io, n = add{ a = 1, b = 2 } }
    match ctxtest_op_typed{ which = 1 } {
        null => { io::println{ &io, s = "missing" } }
        some{ value = mul } => { io::println_i64{ &io, n = mul{ a = 3, b = 3 } } }
    }
    io::println_i64{ &io, n = @as(i64, @size_of(?Op)) }
}
"""), "42\nnull\n3\n9\n8\n")

    def test_named_extern_as_a_value(self):
        self.assertEqual(self.run_with_lib("""
fn main { mut io: Io } {
    io::println_i64{ &io, n = ctxtest_apply{ f = ctxtest_sub, a = 10, b = 4 } }
    let sub: Op = ctxtest_sub
    io::println_i64{ &io, n = ctxtest_apply{ f = sub, a = 1, b = 4 } }
    let mut got: i32 = 0
    ctxtest_out{ f = sub, out = &got }
    io::println_i64{ &io, n = got }
    let maybe: ?Op = ctxtest_sub
    if maybe != null { io::println_i64{ &io, n = maybe{ a = 9, b = 9 } } }
}
"""), "6\n-3\n-2\n0\n")

    def test_errors(self):
        h = 'extern fn labs { n: i64 } -> i64\n'
        for src, msg, line, col in [
            ('struct S { f: extern fn{ x: ?i32 } }\nfn main {} {}',
             "an extern fn type can't pass `x` to C: it has type ?i32, which C has no equivalent of", 1, 26),
            ('struct S { f: extern fn{} -> [4]u8 }\nfn main {} {}',
             "an extern fn type can't return [4]u8: C has no equivalent of it", 1, 30),
            (h + 'fn main {} { let f: extern fn{ n: i64 } -> i64 = labs\n  _ = f{ m = 1 } }', '`f` has no field `m`', 3, 10),
            ('fn g { n: i64 } -> i64 { return n }\nfn main {} { let f: extern fn{ n: i64 } -> i64 = g }',
             "a ctxlang function can't be passed as a C function pointer (extern fn{ n: i64 } -> i64): only an extern fn or a `#c::callback` fn can", 2, 50),
            (h + 'fn main {} { let h: extern fn{ n: i64 } -> i64 = labs\n  let k: fn{ n: i64 } -> i64 = h }',
             "a C function pointer (extern fn{ n: i64 } -> i64) can't be used as a ctxlang fn{ n: i64 } -> i64", 3, 32),
            (h + 'fn main {} { let f: extern fn{ n: i32 } -> i64 = labs }',
             'expected extern fn{ n: i32 } -> i64, got extern fn{ n: i64 } -> i64', 2, 50),
            (h + 'fn main {} { let f: extern fn{ n: i64 } -> i64 = labs\n  let g = f{ _ } }',
             "a C function pointer can't be bound with `_`: call it with every field", 3, 12),
            ('fn main {} { let x: i32 = 5\n  let f = @cast(extern fn{}, x) }', '@cast needs a pointer or extern fn argument', 2, 30),
            ('fn main {} { let p: ?*u8 = null\n  let f = @cast(extern fn{}, p) }',
             "@cast needs a value that isn't null: check the optional first", 2, 30),
            ('fn g {} {}\nfn main {} { let f = @cast(*u8, g) }',
             "@cast can't take a ctxlang function: only a pointer or an extern fn value", 2, 33),
            ('fn main {} { let f = @cast(fn{}, 0) }', '@cast needs a pointer or extern fn target type, got fn{}', 1, 22),
        ]:
            self.assertCfnError(src, msg, line, col)

    def test_type_identity_is_ordered(self):
        self.assertCfnError('extern fn f { a: i32, b: i32 }\nfn main {} { let g: extern fn{ b: i32, a: i32 } = f }',
            'expected extern fn{ b: i32, a: i32 }, got extern fn{ a: i32, b: i32 }', 2, 51)


class Callbacks(CLib):
    """`#c::callback` (spec §12, §18): a ctxlang fn that C calls through a pointer, converted
    where an extern fn type is expected."""

    LIB_C = """
#include <stdint.h>
int32_t ctxtest_apply(int32_t (*f)(int32_t, int32_t), int32_t a, int32_t b) { return f(a, b); }
void ctxtest_each(void (*f)(int64_t *, int32_t), int64_t *user, int32_t n) {
    for (int32_t i = 1; i <= n; i++) f(user, i);
}
typedef struct { int32_t x, y; } P;
P ctxtest_swap(P (*f)(P), P p) { return f(p); }
"""

    HEAD = """
type Op = extern fn{ a: i32, b: i32 } -> i32
extern fn ctxtest_apply { f: Op, a: i32, b: i32 } -> i32
extern fn ctxtest_each { f: extern fn{ mut total: i64, i: i32 }, mut total: i64, n: i32 }
"""

    def test_qsort(self):
        self.assertOutput("""
extern fn qsort { base: *mut u8, n: usize, size: usize, cmp: extern fn{ a: *u8, b: *u8 } -> i32 }

#c::callback
fn descending { a: *u8, b: *u8 } -> i32 {
    let x = @cast(*i32, a).*
    let y = @cast(*i32, b).*
    return if x < y { 1 } else if x > y { -1 } else { 0 }
}

fn main { mut io: Io } {
    let mut xs: [5]i32 = [3, 1, 4, 1, 5]
    qsort{ base = @cast(*mut u8, &xs), n = 5, size = 4, cmp = descending }
    let mut i: usize = 0
    while i < 5 { io::println_i64{ &io, n = xs[i] }; i = i + 1 }
}
""", "5\n4\n3\n1\n1\n")

    def test_called_from_c(self):
        self.assertEqual(self.run_with_lib("""
#c::symbol{ name = "ctxtest_apply" }
extern fn apply_io { f: extern fn{ mut io: Io, a: i32, b: i32 } -> i32, a: i32, b: i32 } -> i32

struct P { x: i32, y: i32 }
#c::symbol{ name = "ctxtest_swap" }
extern fn swap_via { f: extern fn{ p: P } -> P, p: P } -> P

// Fields of the type it doesn't take are dropped: this one ignores `a`.
#c::callback
fn twice { b: i32 } -> i32 { return b * 2 }

#c::callback
fn sub { a: i32, b: i32 } -> i32 { return a - b }

// A capability in the type is supplied, not passed by C.
#c::callback
fn noisy { mut io: Io, a: i32, b: i32 } -> i32 {
    io::println_i64{ &io, n = a }
    return a + b
}

// A `mut` field is C's pointer: here, the user data.
#c::callback
fn add_to { mut total: i64, i: i32 } { total = total + @as(i64, i) }

#c::callback
fn swap { p: P } -> P { return P{ x = p.y, y = p.x } }

fn main { mut io: Io } {
    io::println_i64{ &io, n = ctxtest_apply{ f = twice, a = 100, b = 21 } }
    io::println_i64{ &io, n = ctxtest_apply{ f = sub, a = 10, b = 4 } }
    let op: Op = sub
    let maybe: ?Op = twice
    if maybe != null { io::println_i64{ &io, n = maybe{ a = 0, b = 5 } } }
    io::println_i64{ &io, n = op{ a = 1, b = 3 } }
    io::println_i64{ &io, n = apply_io{ f = noisy, a = 7, b = 8 } }
    let mut total: i64 = 0
    ctxtest_each{ f = add_to, &total, n = 4 }
    io::println_i64{ &io, n = total }
    let q = swap_via{ f = swap, p = P{ x = 1, y = 2 } }
    io::println_i64{ &io, n = q.x * 10 + q.y }
    // Still an ordinary fn to ctxlang.
    io::println_i64{ &io, n = sub{ a = 3, b = 1 } }
}
"""), "42\n6\n10\n-2\n7\n15\n10\n21\n2\n")

    def test_errors(self):
        for src, msg, line, col in [
            ('#c::callback\nextern fn f { n: i64 }\nfn main {} {}',
             '`c::callback` applies only to a fn with a body, not an extern fn', 1, 1),
            ('#c::callback\nstruct S {}\nfn main {} {}', '`c::callback` applies only to a fn', 1, 1),
            ('#c::callback\n#c::callback\nfn f {} {}\nfn main {} {}', 'duplicate `c::callback` attribute', 2, 1),
            ('#c::callback\nfn f(T) { x: T } {}\nfn main {} {}', "a `c::callback` fn can't be generic", 1, 1),
            ('#c::callback\nfn f { x: ?i32 } {}\nfn main {} {}',
             "callback `f` can't pass `x` to C: it has type ?i32, which C has no equivalent of", 2, 8),
            ('#c::callback\nfn f {} -> [2]u8 { return [0, 0] }\nfn main {} {}',
             "callback `f` can't return [2]u8: C has no equivalent of it", 2, 12),
            ('#c::callback\nfn g { m: i64 } -> i64 { return m }\nfn main {} { let f: extern fn{ n: i64 } -> i64 = g }',
             'expected extern fn{ n: i64 } -> i64, got extern fn{ m: i64 } -> i64', 3, 50),
            ('#c::callback\nfn g { n: i64 } {}\nfn main {} { let f: extern fn{ n: i64 } -> i64 = g }',
             'expected extern fn{ n: i64 } -> i64, got extern fn{ n: i64 }', 3, 50),
            ('#c::callback\nfn g { mut n: i64 } {}\nfn main {} { let f: extern fn{ n: i64 } = g }',
             'expected extern fn{ n: i64 }, got extern fn{ mut n: i64 }', 3, 43),
            # Only the name converts: a fn value has no C function behind it.
            ('#c::callback\nfn g { n: i64 } {}\nfn main {} { let h = g\n  let f: extern fn{ n: i64 } = h }',
             "a ctxlang function can't be passed as a C function pointer (extern fn{ n: i64 }): only an extern fn or a `#c::callback` fn can", 4, 32),
        ]:
            self.assertCfnError(src, msg, line, col)


class UntaggedUnions(Base):
    """`extern union` (spec §12, Untagged unions): C's union, every field at offset 0, checked
    against C through a static library built in the test."""

    LIB_C = """
#include <stddef.h>
#include <stdint.h>
typedef struct { float r, g, b, a; } Color;
typedef struct { float depth; uint32_t stencil; } DepthStencil;
typedef union { Color color; DepthStencil depth_stencil; } ClearValue;
typedef struct { uint32_t kind; ClearValue value; uint8_t last; } Attachment;
uint64_t ctxtest_size(void) { return sizeof(ClearValue); }
uint64_t ctxtest_align(void) { return _Alignof(ClearValue); }
uint64_t ctxtest_attachment_size(void) { return sizeof(Attachment); }
uint64_t ctxtest_last_offset(void) { return offsetof(Attachment, last); }
ClearValue ctxtest_depth(float d, uint32_t s) { ClearValue v = { 0 }; v.depth_stencil.depth = d; v.depth_stencil.stencil = s; return v; }
float ctxtest_sum(ClearValue v) { return v.color.r + v.color.g + v.color.b + v.color.a; }
uint32_t ctxtest_attachment(Attachment a) { return a.kind * 1000 + a.value.depth_stencil.stencil * 10 + a.last; }
"""

    BUILD = CFunctionPointers.BUILD

    HEAD = """
struct Color { r: f32, g: f32, b: f32, a: f32 }
struct DepthStencil { depth: f32, stencil: u32 }
extern union ClearValue { color: Color, depth_stencil: DepthStencil }
struct Attachment { kind: u32, value: ClearValue, last: u8 }
extern fn ctxtest_size {} -> u64
extern fn ctxtest_align {} -> u64
extern fn ctxtest_attachment_size {} -> u64
extern fn ctxtest_last_offset {} -> u64
extern fn ctxtest_depth { d: f32, s: u32 } -> ClearValue
extern fn ctxtest_sum { v: ClearValue } -> f32
extern fn ctxtest_attachment { a: Attachment } -> u32
"""

    def run_with_lib(self, main):
        return CFunctionPointers.run_with_lib(self, main)

    def assertUnionError(self, src, msg, line, col):
        with self.assertRaises(CompileError) as cm:
            run(src)
        self.assertEqual((cm.exception.msg, cm.exception.pos[:2]), (msg, (line, col)), src)

    def test_layout_matches_c(self):
        self.assertEqual(self.run_with_lib("""
fn main { mut io: Io } {
    io::println_u64{ &io, n = ctxtest_size{} - @size_of(ClearValue) }
    io::println_u64{ &io, n = ctxtest_align{} - @align_of(ClearValue) }
    io::println_u64{ &io, n = ctxtest_attachment_size{} - @size_of(Attachment) }
    io::println_u64{ &io, n = @size_of(ClearValue) }
    io::println_u64{ &io, n = ctxtest_last_offset{} }
}
"""), "0\n0\n0\n16\n20\n")

    def test_by_value_both_ways(self):
        self.assertEqual(self.run_with_lib("""
fn main { mut io: Io } {
    let v = ctxtest_depth{ d = 0.5, s = 7 }
    io::println_f64{ &io, n = v.depth_stencil.depth }
    io::println_u64{ &io, n = v.depth_stencil.stencil }
    let c = ClearValue{ color = Color{ r = 1.0, g = 2.0, b = 3.0, a = 4.0 } }
    io::println_f64{ &io, n = ctxtest_sum{ v = c } }
    let a = Attachment{ kind = 3, value = ClearValue{ depth_stencil = DepthStencil{ depth = 1.0, stencil = 5 } }, last = 9 }
    io::println_u64{ &io, n = ctxtest_attachment{ a } }
}
"""), "0.5\n7\n10.0\n3059\n")

    def test_fields_share_bytes(self):
        self.assertOutput("""
extern union Bits { f: f32, u: u32, b: u8 }
struct Holder { tag: u8, bits: Bits }
fn main { mut io: Io } {
    io::println_u64{ &io, n = @size_of(Bits) + @align_of(Bits) * 10 }
    // a literal sets one field; the other bytes are zero
    let mut x = Bits{ b = 255 }
    io::println_u64{ &io, n = x.u }
    x.f = 1.0
    io::println_u64{ &io, n = x.u }
    // the zero value: every byte zero
    let mut z: Bits
    io::println_u64{ &io, n = z.u }
    let mut h = Holder{ tag = 1, bits = Bits{ u = 7 } }
    h.bits.b = 9
    io::println_u64{ &io, n = h.bits.u }
    let p = &h.bits
    io::println_u64{ &io, n = p.u }
}
""", "44\n255\n1065353216\n0\n9\n9\n")

    def test_errors(self):
        U = 'extern union U { a: i32, b: f32 }\n'
        for src, msg, line, col in [
            (U + 'fn main {} { let u = U{ a = 1, b = 2.0 } }', 'extern union `U` literal must set exactly one field', 2, 23),
            (U + 'fn main {} { let u = U{} }', 'extern union `U` literal must set exactly one field', 2, 23),
            (U + 'fn main {} { let u = U{ a = 1 }\n    match u { a => {} } }',
             'an extern union has no tag to match on: read the field you know it holds', 3, 11),
            (U + 'fn main {} { let u = U{ a = 1 }\n    let a{ x } = u else { return } }',
             'an extern union has no tag to match on: read the field you know it holds', 3, 18),
            ('extern union U(T) { a: T }\nfn main {} {}', 'an extern union cannot have generic parameters', 1, 15),
            (U + 'fn f { mut x: i32, mut y: f32 } {}\nfn main {} { let mut u = U{ a = 1 }\n    f{ x = &u.a, y = &u.b } }',
             'two mut references to `u.a` in one call', 4, 6),
            (U + 'const C: U = U{ a = 1 }\nfn main {} {}', 'a const cannot hold an extern union', 2, 15),
            ('struct P { p: *i32 }\nextern union V { a: i32, p: P }\nfn main { mut io: Io } { let mut v: V\n    io::println_i64{ &io, n = v.a } }',
             '`v` may be read before it is assigned', 4, 31),
        ]:
            self.assertUnionError(src, msg, line, col)


class CStrings(Base):
    """`c::String` (spec §11 Literals, §18): C's NUL-terminated `const char *`. A literal where one
    is expected gets a NUL, and `?c::String` is a pointer whose null is NULL."""

    LIB_C = """
#include <stdint.h>
#include <string.h>
typedef struct { const char *name; int32_t n; } Named;
typedef const char *(*Pick)(int32_t);
static const char *pick(int32_t i) { return i ? "one" : NULL; }
uint64_t ctxtest_named(Named x) { return x.name ? strlen(x.name) * 10 + (uint64_t)x.n : (uint64_t)x.n; }
const char *ctxtest_echo(const char *s) { return s; }
Pick ctxtest_picker(void) { return pick; }
"""

    BUILD = CFunctionPointers.BUILD

    HEAD = """
struct Named { name: ?c::String, n: i32 }
type Pick = extern fn{ i: i32 } -> ?c::String
extern fn ctxtest_named { x: Named } -> u64
extern fn ctxtest_echo { s: ?c::String } -> ?c::String
extern fn ctxtest_picker {} -> Pick
"""

    def run_with_lib(self, main):
        return CFunctionPointers.run_with_lib(self, main)

    def test_literals_to_libc(self):
        self.assertOutput("""
extern fn strlen { s: c::String } -> usize
extern fn strcmp { a: c::String, b: c::String } -> i32
extern fn strchr { s: c::String, ch: i32 } -> ?c::String
const GREETING: c::String = "hello"
fn pick { b: bool } -> c::String { return if b { "yes" } else { "no" } }
fn main { mut io: Io } {
    io::println_u64{ &io, n = strlen{ s = "hello" } }
    io::println_i64{ &io, n = strcmp{ a = "abc", b = "abc" } }
    io::println_u64{ &io, n = strlen{ s = GREETING } + strlen{ s = pick{ b = true } } }
    let hit = strchr{ s = "hello", ch = 'l' }
    match hit {
        null => { io::println{ &io, s = "none" } }
        some{ value } => { io::println{ &io, s = utf8::of{ chars = c::bytes{ s = value } } } }
    }
    io::println_bool{ &io, n = strchr{ s = "hello", ch = 'z' } == null }
}
""", "5\n0\n8\nllo\ntrue\n")

    def test_helpers(self):
        self.assertOutput("""
fn main { mut io: Io } {
    let s: c::String = "abc"
    io::println_u64{ &io, n = c::len{ s } }
    io::println{ &io, s = utf8::of{ chars = c::bytes{ s } } }
    io::println_u64{ &io, n = c::len{ s = "" } }
    let mut mem: [16]u8
    let mut heap = arena::new{ buf = mem[..] }
    let ok{ value = t } = c::copy{ realloc = arena::alloc, &heap, bytes = "built" } else { return }
    io::println_u64{ &io, n = c::len{ s = t } }
    let bad: []u8 = "a\\0b"
    match c::copy{ realloc = arena::alloc, &heap, bytes = bad } {
        ok => {}
        err{ error } => {
            match error {
                c::has_nul{ at } => { io::println_u64{ &io, n = at } }
                c::out_of_memory => { io::println{ &io, s = "oom" } }
            }
        }
    }
    let big: []u8 = "this does not fit in what is left"
    match c::copy{ realloc = arena::alloc, &heap, bytes = big } {
        ok               => {}
        c::has_nul       => {}
        c::out_of_memory => { io::println{ &io, s = "oom" } }
    }
}
""", "3\nabc\n0\n5\n1\noom\n")

    def test_nullable_and_layout(self):
        self.assertOutput("""
const NONE: ?c::String = null
const SOME: ?c::String = "set"
fn main { mut io: Io } {
    io::println_u64{ &io, n = @size_of(?c::String) + @size_of(c::String) }
    let mut z: ?c::String
    let s = SOME
    io::println_bool{ &io, n = z == null and NONE == null and s != null }
    if s != null { io::println_u64{ &io, n = c::len{ s } } }
    z = "now"
    let some{ value = v } = z else { return }
    io::println_u64{ &io, n = c::len{ s = v } }
}
""", "16\ntrue\n3\n3\n")

    def test_across_c(self):
        self.assertEqual(self.run_with_lib("""
fn main { mut io: Io } {
    io::println_u64{ &io, n = ctxtest_named{ x = Named{ name = "four", n = 2 } } }
    io::println_u64{ &io, n = ctxtest_named{ x = Named{ name = null, n = 7 } } }
    io::println_bool{ &io, n = ctxtest_echo{ s = null } == null }
    let e = ctxtest_echo{ s = "back" }
    if e != null { io::println{ &io, s = utf8::of{ chars = c::bytes{ s = e } } } }
    let pick = ctxtest_picker{}
    let one = pick{ i = 1 }
    if one != null { io::println_u64{ &io, n = c::len{ s = one } } }
    io::println_bool{ &io, n = pick{ i = 0 } == null }
}
"""), "42\n7\ntrue\nback\n3\ntrue\n")

    def test_nul_in_a_literal(self):
        with self.assertRaises(CompileError) as cm:
            run('extern fn puts { s: c::String } -> i32\nfn main {} { _ = puts{ s = "a\\0b" } }')
        self.assertEqual((cm.exception.msg, cm.exception.pos[:2]),
                         ("a C string literal can't hold a NUL byte (byte 1): C would end the string there", (2, 28)))


class WordCountExample(Base):
    def setUp(self):
        import tempfile
        with open(os.path.join(ROOT, 'examples', 'wordcount.ctx'), encoding='utf-8') as f:
            self.src = f.read()
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def run_wc(self, args):
        out, err = io.StringIO(), io.StringIO()
        code = run_source(self.src, out=out, err=err, args=args)
        return out.getvalue(), err.getvalue(), code

    def test_counts(self):
        p = os.path.join(self.tmp.name, 'words.txt')
        with open(p, 'wb') as f:
            f.write(b'The cat and the dog.\nA cat, the bird!\nand THE end')
        self.assertEqual(self.run_wc([p]),
                         ('lines: 3\nwords: 12\ndistinct: 7\nmost common: the 4\n', '', 0))

    def test_tie_goes_to_alphabetically_first(self):
        p = os.path.join(self.tmp.name, 'tie.txt')
        with open(p, 'wb') as f:
            f.write(b'b a b a c\n')
        self.assertEqual(self.run_wc([p])[0], 'lines: 1\nwords: 5\ndistinct: 3\nmost common: a 2\n')

    def test_usage(self):
        self.assertEqual(self.run_wc([]), ('', 'usage: wordcount FILE\n', 2))

    def test_missing_file(self):
        out, err, code = self.run_wc([os.path.join(self.tmp.name, 'nope.txt')])
        self.assertEqual((out, code), ('', 1))
        self.assertTrue(err.endswith('nope.txt: no such file\n'))

    def test_utf8_words(self):
        p = os.path.join(self.tmp.name, 'utf8.txt')
        with open(p, 'wb') as f:
            f.write('Café au lait, café noir. Naïve café!\n'.encode('utf-8'))
        self.assertEqual(self.run_wc([p])[0], 'lines: 1\nwords: 7\ndistinct: 5\nmost common: café 3\n')

    def test_not_utf8(self):
        p = os.path.join(self.tmp.name, 'bin')
        with open(p, 'wb') as f:
            f.write(b'caf\xe9')
        self.assertEqual(self.run_wc([p]), ('', 'not a UTF-8 text file\n', 1))


class JsonExample(Base):
    """examples/json: a program made of a directory of files."""

    def setUp(self):
        import tempfile
        self.sources = read_program(os.path.join(ROOT, 'examples', 'json'))
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def run_json(self, text, *query):
        p = os.path.join(self.tmp.name, 'in.json')
        with open(p, 'wb') as f:
            f.write(text if isinstance(text, bytes) else text.encode('utf-8'))
        out, err = io.StringIO(), io.StringIO()
        code = run_sources(self.sources, out=out, err=err, args=[p, *query])
        return out.getvalue(), err.getvalue().replace(p, 'in.json'), code

    def test_loads_every_file(self):
        names = sorted(os.path.basename(f) for _, f in self.sources)
        self.assertEqual(names, ['main.ctx', 'parser.ctx', 'printer.ctx', 'value.ctx'])

    def test_pretty_prints(self):
        self.assertEqual(self.run_json('{"a":[1,2.5,{}],"b":{"c":null,"d":[]},"e":true}'), ('''{
  "a": [
    1,
    2.5,
    {}
  ],
  "b": {
    "c": null,
    "d": []
  },
  "e": true
}
''', '', 0))

    def test_numbers(self):
        for text, expected in [('-0', '0'), ('1E+2', '100'), ('-1.5e-3', '-0.0015'), ('1e300', '1e+300'),
                               ('123456789012345678', '1.2345678901234568e+17')]:
            self.assertEqual(self.run_json(text), (expected + '\n', '', 0), text)

    def test_strings(self):
        self.assertEqual(self.run_json(r'"t\t \"q\" \\ \/ é 😀 \u001f"')[0],
                         r'"t\t \"q\" \\ / é 😀 \u001f"' + '\n')
        self.assertEqual(self.run_json('"Zoë ☃"')[0], '"Zoë ☃"\n')

    def test_lookup(self):
        doc = '{"users": [{"name": "Ada"}, {"name": "Zoë", "x": 1, "x": 2}]}'
        self.assertEqual(self.run_json(doc, 'users.1.name'), ('"Zoë"\n', '', 0))
        self.assertEqual(self.run_json(doc, 'users.1.x'), ('2\n', '', 0))       # the last duplicate wins
        self.assertEqual(self.run_json(doc, 'users.2'), ('', 'no value at users.2\n', 1))
        self.assertEqual(self.run_json(doc, 'users.name'), ('', 'no value at users.name\n', 1))

    def test_errors(self):
        for text, expected in [
            ('[1, 2,]', '1:7: expected a value'),
            ('{"a" 1}', "1:6: expected ':'"),
            ('{"a":1,}', '1:8: expected a string key'),
            ('[1 2]', "1:4: expected ',' or ']'"),
            ('{"a":1 "b":2}', "1:8: expected ',' or '}'"),
            ('[01]', '1:2: invalid number'),
            ('1.', '1:1: invalid number'),
            ('1e999', '1:1: invalid number'),
            (r'"\x"', '1:2: invalid escape'),
            (r'"\ud800"', '1:2: invalid escape'),
            (r'"\udc00"', '1:2: invalid escape'),
            ('"a\tb"', '1:3: control character in string'),
            ('"abc', '1:5: unexpected end of input'),
            ('', '1:1: unexpected end of input'),
            ('[1] 2', '1:5: unexpected text after the value'),
            ('{\n  "é": [1,\n     "é", tru]}', '3:11: expected a value'),
        ]:
            self.assertEqual(self.run_json(text), ('', 'in.json:' + expected + '\n', 1), text)

    def test_not_utf8(self):
        self.assertEqual(self.run_json(b'"caf\xe9"'), ('', 'in.json:1:5: not UTF-8 text\n', 1))

    def test_usage(self):
        err = io.StringIO()
        self.assertEqual(run_sources(self.sources, out=io.StringIO(), err=err, args=[]), 2)
        self.assertEqual(err.getvalue(), 'usage: json FILE [PATH]\n')


if __name__ == '__main__':
    unittest.main()
