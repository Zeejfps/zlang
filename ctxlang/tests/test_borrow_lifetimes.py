"""Direct borrowing summaries and invocation-owned borrowed callback records."""
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from toolchain import CompileError, build_sources, run_source

cases = {}
def case(name, expected, source, output=None):
    cases[name] = (expected, source, output)
case('ignored_argument_static', True, '''
fn lookup { key: []u8 } -> []u8 { return "static" }
fn load {} -> []u8 { let buf: [3]u8 = [1,2,3]; return lookup{ key = buf[..] } }
fn main {} { _ = load{} }
''')
case('late_declared_static', True, '''
fn load {} -> []u8 { let buf: [3]u8 = [1,2,3]; return lookup{ key = buf[..] } }
fn lookup { key: []u8 } -> []u8 { return "static" }
fn main {} { _ = load{} }
''')
case('static_error', True, '''
error bad{ text: []u8 }
fn check { data: []u8 } -> ! { if data.len > 0 { return bad{ text = "bad" } } }
fn load {} -> ! { let buf: [3]u8 = [1,2,3]; try check{ data = buf[..] } }
fn main {} { _ = load{} }
''')
case('success_borrows_error_static', True, '''
error bad{ text: []u8 }
fn parse { data: []u8 } -> ![]u8 { if data.len == 0 { return bad{ text = "bad" } }; return data }
fn load {} -> !u8 { let buf: [3]u8 = [1,2,3]; let s = try parse{ data = buf[..] }; return s[0] }
fn main {} { _ = load{} }
''')
case('direct_real_borrow', False, '''
fn view { s: []u8 } -> []u8 { return s }
fn load {} -> []u8 { let buf: [3]u8 = [1,2,3]; return view{ s = buf[..] } }
fn main {} { _ = load{} }
''')
case('callback_real_borrow', False, '''
fn view { s: []u8 } -> []u8 { return s }
fn load {} -> []u8 { let buf: [3]u8 = [1,2,3]; let call = view{ s = buf[..], _ }; return call{} }
fn main {} { _ = load{} }
''')
case('callback_error_borrow', False, '''
error bad{ text: []u8 }
fn fail { s: []u8 } -> ! { return bad{ text = s } }
fn load {} -> ! { let buf: [3]u8 = [1,2,3]; let call = fail{ s = buf[..], _ }; try call{} }
fn main {} { _ = load{} }
''')
case('nested_bind_borrow', False, '''
fn view { s: []u8, n: i32 } -> []u8 { return s }
fn load {} -> []u8 { let buf: [3]u8 = [1,2,3]; let call = view{ s = buf[..], _ }; let again = call{ n = 0, _ }; return again{} }
fn main {} { _ = load{} }
''')
case('mut_store_then_read', False, '''
struct Holder { s: []u8 }
fn store { mut h: Holder, s: []u8 } -> []u8 { h.s = s; return h.s }
fn load { mut h: Holder } -> []u8 { let buf: [3]u8 = [1,2,3]; return store{ &h, s = buf[..] } }
fn main {} { let mut h: Holder; _ = load{ &h } }
''')
case('transitive_store_then_read', False, '''
struct Holder { s: []u8 }
fn put { mut h: Holder, s: []u8 } { h.s = s }
fn store { mut h: Holder, s: []u8 } -> []u8 { put{ &h, s }; return h.s }
fn load { mut h: Holder } -> []u8 { let buf: [3]u8 = [1,2,3]; return store{ &h, s = buf[..] } }
fn main {} { let mut h: Holder; _ = load{ &h } }
''')
case('recursive_real_borrow', False, '''
fn first { s: []u8, n: i32 } -> []u8 { if n > 0 { return second{ s, n = n - 1 } }; return s }
fn second { s: []u8, n: i32 } -> []u8 { return first{ s, n } }
fn load {} -> []u8 { let buf: [3]u8 = [1,2,3]; return first{ s = buf[..], n = 1 } }
fn main {} { _ = load{} }
''')
case('loop_snapshots', True, '''
fn read { n: i32 } -> i32 { return n }
fn main { mut io: Io } {
    let mut first = read{ n = -1, _ }
    let mut last = read{ n = -1, _ }
    let mut i: i32 = 0
    while i < 3 {
        let call = read{ n = i, _ }
        if i == 0 { first = call } else { last = call }
        i = i + 1
    }
    io::println_i64{ &io, n = first{} }
    io::println_i64{ &io, n = last{} }
}
''', '0\n2\n')
case('nested_call_preserves_outer_callback', True, '''
fn read { n: i32 } -> i32 { return n }
fn inner { call: &fn{} -> i32 } -> i32 { let other = read{ n = 4, _ }; return call{} + other{} }
fn outer {} -> i32 { let call = read{ n = 7, _ }; return inner{ call } + call{} }
fn main { mut io: Io } { io::println_i64{ &io, n = outer{} } }
''', '18\n')
case('defer_uses_callback_before_free', True, '''
fn read { n: i32 } -> i32 { return n }
fn work { mut io: Io } -> i32 {
    let call = read{ n = 7, _ }
    defer io::println_i64{ &io, n = call{} }
    return call{}
}
fn main { mut io: Io } { io::println_i64{ &io, n = work{ &io } } }
''', '7\n7\n')
case('generic_identity_borrow', False, '''
fn identity(T) { x: T } -> T { return x }
fn load {} -> []u8 { let buf: [3]u8 = [1,2,3]; return identity{ x = buf[..] } }
fn main {} { _ = load{} }
''')
case('lookup_ignores_key', True, '''
fn get { items: [][]u8, key: []u8 } -> []u8 { if key.len == 0 { return "none" }; return items[0] }
fn load { items: [][]u8 } -> []u8 { let buf: [3]u8 = [1,2,3]; return get{ items, key = buf[..] } }
fn main {} { let items: [1][]u8 = ["okay"]; _ = load{ items = items[..] } }
''')
case('lookup_preserves_collection_borrow', False, '''
fn get { items: [][]u8, key: []u8 } -> []u8 { if key.len == 0 { return "none" }; return items[0] }
fn load {} -> []u8 { let buf: [3]u8 = [1,2,3]; let items: [1][]u8 = [buf[..]]; return get{ items = items[..], key = "key" } }
fn main {} { _ = load{} }
''')
case('byte_copy_allocates_independently', True, '''
fn copy { mut heap: arena::Arena, s: []u8 } -> ![]mut u8 {
    let out = try alloc::resize(u8, arena::Arena){ realloc = arena::alloc, &heap, mem = slice::empty(u8){}, count = s.len }
    slice::copy(u8){ dst = out, src = s }
    return out
}
fn load { mut heap: arena::Arena } -> ![]mut u8 { let buf: [3]u8 = [1,2,3]; return try copy{ &heap, s = buf[..] } }
fn main {} { let mut mem: [1024]u8; let mut heap = arena::Arena{ buf = mem[..], used = 0 }; _ = load{ &heap } }
''')
case('narrowed_optional_retains_borrow', False, '''
fn unwrap { s: ?[]u8 } -> []u8 { if s != null { return s }; return "" }
fn load {} -> []u8 { let buf: [3]u8 = [1,2,3]; return unwrap{ s = buf[..] } }
fn main {} { _ = load{} }
''')
case('try_argument_uses_success_origins', False, '''
error bad{ text: []u8 }
fn view { s: []u8 } -> []u8 { return s }
fn fail { s: []u8 } -> ! { return bad{ text = s } }
fn load {} -> ! { let buf: [3]u8 = [1,2,3]; try fail{ s = view{ s = buf[..] } } }
fn main {} { _ = load{} }
''')
case('callback_capture_store_effect', False, '''
struct Holder { s: []u8 }
fn put { mut h: Holder, s: []u8 } { h.s = s }
fn invoke { f: &fn{}, h: *Holder } -> []u8 { f{}; return h.s }
fn load { h: *mut Holder } -> []u8 {
    let buf: [3]u8 = [1,2,3]
    let callback = put{ h, s = buf[..], _ }
    return invoke{ f = callback, h }
}
fn main {} { let mut h: Holder; _ = load{ h = &h } }
''')

case('address_of_slice_element_borrows_input', False, '''
fn first { s: []u8 } -> *u8 { return &s[0] }
fn load {} -> *u8 { let buf: [3]u8 = [1,2,3]; return first{ s = buf[..] } }
fn main {} { _ = load{} }
''')
case('try_panic_keeps_only_success_origins', True, '''
error bad{ text: []u8 }
fn fresh { s: []u8 } -> ![]u8 { if s.len == 0 { return bad{ text = s } }; let text: []u8 = "static"; return text }
fn load {} -> []u8 { let buf: [3]u8 = [1,2,3]; return try! fresh{ s = buf[..] } }
fn main {} { _ = load{} }
''')

review_cases={
'direct_projection':"""error bad{ p: *i32 }
struct Last { r: !*i32 }
fn mk { p: *i32 } -> Last { return Last{ r = bad{ p } } }
fn leak {} -> ! { let x: i32 = 1; _ = try mk{ p = &x }.r }
fn main {} { _ = leak{} }
""",
'relay_projection':"""error bad{ p: *i32 }
struct Last { r: !*i32 }
fn mk { p: *i32 } -> Last { return Last{ r = bad{ p } } }
fn relay { p: *i32 } -> !*i32 { return mk{ p }.r }
fn leak {} -> ! { let x: i32 = 1; _ = try relay{ p = &x } }
fn main {} { _ = leak{} }
""",
'generic_error':"""error bad{ p: *i32 }
fn id(T) { x: T } -> T { return x }
fn leak {} -> ! { let x: i32 = 1; let r: !*i32 = bad{p=&x}; _ = try id{ x=r } }
fn main {} { _ = leak{} }
""",
'array_error':"""error bad{ p: *i32 }
fn wrap { p: *i32 } -> [1]!*i32 { return [bad{ p }] }
fn relay { p: *i32 } -> !*i32 { return wrap{ p }[0] }
fn leak {} -> ! { let x: i32 = 1; _ = try relay{ p=&x } }
fn main {} { _ = leak{} }
"""}
review_cases['generic_error_relay'] = """error bad{ p: *i32 }
fn id(T) { x: T } -> T { return x }
fn relay { p: *i32 } -> ! { let r: !*i32 = bad{p}; _ = try id{ x=r } }
fn leak {} -> ! { let x: i32=1; try relay{p=&x} }
fn main {} { _ = leak{} }
"""
review_cases['optional_error_relay'] = """error bad{ p: *i32 }
fn maybe { p: *i32 } -> ?error { let e:error=bad{p}; return e }
fn relay { p: *i32 } -> ?error { return maybe{p} }
fn leak {} -> ?error { let x:i32=1; return relay{p=&x} }
fn main {} { _ = leak{} }
"""

for name, source in review_cases.items():
    case(name, False, source)

case('generic_pointer_store_effect', False, """
struct Box(T) { x: T }
fn stash(T) { mut h: Box(T), x: T } { h.x = x }
fn stored(T) { mut h: Box(T), x: T } -> T { stash{ &h, x }; return h.x }
fn leak { mut h: Box([]u8) } -> []u8 {
    let buf: [3]u8 = [1,2,3]
    return stored{ &h, x = buf[..] }
}
fn main {} { let mut h: Box([]u8); _ = leak{ &h } }
""")
case('escaping_fn_widening_record_lives_after_return', True, """
error failed
fn number {} -> !i32 { return 42 }
fn read { n: i32 } -> i32 { return n }
struct Saved { f: fn{} -> !i32 }
fn make {} -> Saved { let f = number; return Saved{ f } }
fn churn {} { let call = read{ n = 9, _ }; _ = call{} }
fn main { mut io: Io } {
    let saved = make{}
    let mut i = 0
    while i < 100 { churn{}; i = i + 1 }
    io::println_i64{ &io, n = try! saved.f{} }
}
""", '42\n')

# Where records go (ctxc/emit_c.ctx, Records): a record from an earlier run of a site that can
# still be called keeps what it captured.
case('record_snapshot_in_outer_local', True, """
fn read { n: i64 } -> i64 { return n }
fn main { mut io: Io } {
    let mut cur = read{ n = -1, _ }
    let mut prev = cur
    let mut i: i64 = 0
    while i < 3 { prev = cur; cur = read{ n = i, _ }; i = i + 1 }
    io::println_i64{ &io, n = prev{} }
    io::println_i64{ &io, n = cur{} }
}
""", '1\n2\n')
case('record_held_through_another_record', True, """
fn zero {} -> i64 { return 0 }
fn read { n: i64 } -> i64 { return n }
fn invoke { f: &fn{} -> i64 } -> i64 { return f{} }
fn main { mut io: Io } {
    let mut saved: &fn{} -> i64 = zero
    let mut i: i64 = 0
    while i < 2 {
        let inner = read{ n = i + 10, _ }
        let outer = invoke{ f = inner, _ }
        if i == 0 { saved = outer }
        i = i + 1
    }
    io::println_i64{ &io, n = saved{} }
}
""", '10\n')
case('record_chain_past_first_segment', True, """
fn zero {} -> i64 { return 0 }
fn next { previous: &fn{} -> i64, k: i64 } -> i64 { return previous{} + k }
fn main { mut io: Io } {
    let mut f: &fn{} -> i64 = zero
    let mut i: i64 = 0
    while i < 5000 { f = next{ previous = f, k = i, _ }; i = i + 1 }
    io::println_i64{ &io, n = f{} }
}
""", '12497500\n')
case('record_confined_local_called_in_its_own_let', True, """
fn add { a: i64, b: i64 } -> i64 { return a + b }
fn use { f: &fn{ b: i64 } -> i64 } -> i64 { return f{ b = 1 } }
fn main { mut io: Io } {
    let mut s: i64 = 0
    let mut i: i64 = 0
    while i < 1000 {
        let g = add{ a = i, _ }
        s = s + use{ f = g } + g{ b = 2 }
        let h = add{ a = use{ f = g }, _ }
        s = s + h{ b = 0 }
        i = i + 1
    }
    io::println_i64{ &io, n = s }
}
""", '1502500\n')
case('record_from_branches', True, """
fn read { n: i64 } -> i64 { return n }
fn pick { c: bool } -> i64 {
    let f = if c { read{ n = 1, _ } } else { read{ n = 2, _ } }
    return f{}
}
fn main { mut io: Io } {
    io::println_i64{ &io, n = pick{ c = true } + pick{ c = false } * 10 }
    let mut i: i64 = 0
    let mut s: i64 = 0
    while i < 4 {
        let f = if i % 2 == 0 { read{ n = i, _ } } else { read{ n = 100, _ } }
        s = s + f{}
        i = i + 1
    }
    io::println_i64{ &io, n = s }
}
""", '21\n202\n')
case('record_in_defers', True, """
error stop
fn read { n: i64 } -> i64 { return n }
fn show { mut io: Io, f: &fn{} -> i64 } { io::println_i64{ &io, n = f{} } }
fn work { mut io: Io, n: i64 } -> ! {
    defer show{ &io, f = read{ n = n * 100, _ } }
    let mut i: i64 = 0
    while i < 3 {
        defer show{ &io, f = read{ n = n + i, _ } }
        if i == n { return stop }
        i = i + 1
    }
}
fn main { mut io: Io } {
    work{ &io, n = 1 } iferr { io::println_i64{ &io, n = -1 } }
    work{ &io, n = 7 } iferr { io::println_i64{ &io, n = -1 } }
}
""", '2\n2\n100\n-1\n8\n9\n10\n700\n')
case('record_slots_per_invocation', True, """
fn read { n: i64 } -> i64 { return n }
fn rec { n: i64, f: &fn{} -> i64 } -> i64 {
    let g = read{ n = n, _ }
    if n == 0 { return f{} }
    let r = rec{ n = n - 1, f = g }
    return r * 10 + g{}
}
fn main { mut io: Io } {
    io::println_i64{ &io, n = rec{ n = 4, f = read{ n = 9, _ } } }
}
""", '11234\n')
case('adapters_of_fn_and_bound_values', True, """
fn one { x: i64 } -> i64 { return x }
fn two { x: i64 } -> i64 { return x * 2 }
struct H { f: fn{ x: i64 } -> i64 }
fn wide { f: fn{ x: i64, extra: i64 } -> i64, x: i64 } -> i64 { return f{ x, extra = 1 } }
fn bwide { f: &fn{ x: i64, extra: i64 } -> i64, x: i64 } -> i64 { return f{ x, extra = 1 } }
fn add { a: i64, x: i64 } -> i64 { return a + x }
fn main { mut io: Io } {
    let hs = [H{ f = one }, H{ f = two }]
    let mut keep: &fn{ x: i64, extra: i64 } -> i64 = add{ a = 0, _ }
    let mut i: i64 = 0
    let mut s: i64 = 0
    while i < 1000 {
        s = s + wide{ f = hs[@as(usize, i % 2)].f, x = i }
        s = s + bwide{ f = add{ a = i, _ }, x = 1 }
        let g: &fn{ x: i64, extra: i64 } -> i64 = add{ a = 1, _ }
        if i == 3 { keep = add{ a = i, _ } }
        s = s + g{ x = 2, extra = 3 }
        i = i + 1
    }
    io::println_i64{ &io, n = s + keep{ x = 0, extra = 0 } }
}
""", '1253003\n')
case('widened_fn_values_in_a_loop', True, """
error bad
fn ok { x: i64 } -> !i64 { if x < 0 { return bad }; return x }
struct H { f: fn{ x: i64 } -> !i64 }
fn call_any { f: fn{ x: i64 } -> !i64, x: i64 } -> i64 { return f{ x } iferr { -1 } }
fn main { mut io: Io } {
    let h = H{ f = ok }
    let mut i: i64 = 0
    let mut s: i64 = 0
    while i < 1000 { s = s + call_any{ f = h.f, x = i - 5 }; i = i + 1 }
    io::println_i64{ &io, n = s }
}
""", '494510\n')
case('big_records_past_first_segment', True, """
struct Big { a: [64]i64 }
fn sum { b: Big, k: i64 } -> i64 { return b.a[0] + b.a[63] + k }
fn main { mut io: Io } {
    let mut fs: &fn{ k: i64 } -> i64 = sum{ b = Big{ a = [0; 64] }, _ }
    let mut keep = fs
    let mut i: i64 = 0
    let mut t: i64 = 0
    while i < 2000 {
        let mut b = Big{ a = [0; 64] }
        b.a[0] = i
        b.a[63] = 1
        keep = fs
        fs = sum{ b, _ }
        t = t + keep{ k = 0 }
        i = i + 1
    }
    io::println_i64{ &io, n = t + fs{ k = 0 } }
}
""", '2001000\n')
case('record_larger_than_a_segment_asks_for_whole_pages', True, """
struct Big { a: [40000]i64 }
fn read { b: Big } -> i64 { return b.a[0] }
#c::callback
fn strict_pages { mut mem: Mem, size: usize } -> ?*mut u8 {
    if size % mem::PAGE != 0 { @panic("record page request is not page-sized") }
    return os::pages{ &mem, size }
}
fn main { mut mem: Mem, mut io: Io } {
    rt::pages_set{ &mem, pages = strict_pages }
    let mut b = Big{ a = [0; 40000] }
    let mut f = read{ b, _ }
    let mut i = 0
    while i < 2 {
        b.a[0] = i + 1
        f = read{ b, _ }
        i = i + 1
    }
    io::println_i64{ &io, n = f{} }
}
""", '2\n')

case('nested_try_preserves_inner_error', False, """
error bad{ p: *i32 }
fn wrap(T) { x: T } -> !T { return x }
fn relay { p: *i32 } -> ! { let r: !*i32 = bad{ p }; _ = try try wrap{ x = r } }
fn leak {} -> ! { let x: i32 = 1; try relay{ p = &x } }
fn main {} { _ = leak{} }
""")
case('nested_try_panic_preserves_inner_error', False, """
error bad{ p: *i32 }
fn wrap(T) { x: T } -> !T { return x }
fn relay { p: *i32 } -> ! { let r: !*i32 = bad{ p }; _ = try try! wrap{ x = r } }
fn leak {} -> ! { let x: i32 = 1; try relay{ p = &x } }
fn main {} { _ = leak{} }
""")

class BorrowSummaries(unittest.TestCase):
    def test_provenance_and_callback_lifetimes(self):
        for name, (accepted, source, output) in cases.items():
            with self.subTest(name=name):
                if not accepted:
                    # Compile only: rejected dangling-pointer probes are never executed.
                    with self.assertRaises(CompileError) as rejected:
                        build_sources([(source, 'borrow.ctx')])
                    self.assertRegex(rejected.exception.msg, r'address|outlives|holds')
                    if name in review_cases:
                        expected = ('returned value holds the address of local `x`' if name == 'optional_error_relay'
                                    else '`try` would return an error that may hold the address of local `x`')
                        self.assertEqual(rejected.exception.msg, expected)
                elif output is None:
                    build_sources([(source, 'borrow.ctx')])
                else:
                    out = io.StringIO()
                    run_source(source, out=out)
                    self.assertEqual(out.getvalue(), output)

    def test_borrowed_records_are_freed_on_normal_and_try_returns(self):
        source = '''
error stopped
fn read { n: i32 } -> i32 { return n }
fn fail {} -> ! { return stopped }
fn invoke { n: i32 } -> ! {
    let mut first = read{ n = -1, _ }
    let mut last = read{ n = -1, _ }
    let mut i = 0
    while i < 3 {
        let call = read{ n = i, _ }
        if i == 0 { first = call } else { last = call }
        i = i + 1
    }
    defer {
        if first{} != 0 or last{} != 2 { @panic("lost callback snapshot") }
    }
    if n % 2 == 0 { try fail{} }
    _ = last{}
}
fn main {} {
    let mut i = 0
    while i < 3000 { _ = invoke{ n = i }; i = i + 1 }
}
'''
        # 3000 invocations borrow 9000 records, more than the runtime's first 64 KiB holds:
        # released on every return, they never need a second segment.
        self.assertRecordsReleased(source)

    def test_frame_slots_take_no_borrowed_records(self):
        # A bind passed to a call, a confined local's and a writer's are frame slots, and an
        # adapter of a named function is static: a loop in main borrows nothing.
        self.assertRecordsReleased('''
fn add { a: i64, b: i64 } -> i64 { return a + b }
fn one { x: i64 } -> i64 { return x }
fn call { f: &fn{ b: i64 } -> i64 } -> i64 { return f{ b = 1 } }
fn wide { f: fn{ x: i64, extra: i64 } -> i64, x: i64 } -> i64 { return f{ x, extra = 1 } }
fn bwide { f: &fn{ b: i64, extra: i64 } -> i64 } -> i64 { return f{ b = 2, extra = 1 } }
fn main { mut io: Io } {
    let mut i: i64 = 0
    let mut s: i64 = 0
    while i < 200000 {
        s = s + call{ f = add{ a = i, _ } } + wide{ f = one, x = i } + bwide{ f = add{ a = i, _ } }
        let g = add{ a = i, _ }
        s = s + g{ b = 1 } + call{ f = g }
        if i % 100000 == 0 { _ = @fmt(&io, "{}\\n", s) }
        i = i + 1
    }
}
''', borrowed=False)

    def assertRecordsReleased(self, source, borrowed=True):
        import pathlib
        import subprocess
        import tempfile
        import toolchain
        # At exit, the record stack is back at the start of the runtime's first segment, which
        # was enough. Without borrowed, main's C borrows no record and adapts nothing.
        wrapper = r'''
#include <stdlib.h>
#include <stdio.h>
#include "ctxrt.h"
static char *base;
static void check(void) {
    if (ctx_recs.seg->next != NULL || ctx_recs.top != base) {
        fprintf(stderr, "records not released\n");
        abort();
    }
}
__attribute__((constructor)) static void install(void) { base = ctx_recs.top; atexit(check); }
'''
        with tempfile.TemporaryDirectory(dir=toolchain.CACHE) as tmp:
            d = pathlib.Path(tmp)
            (d / 'main.ctx').write_text(source)
            code, err = toolchain.ctxc_build(toolchain.native_ctxc(), str(d / 'program.c'), ['main.ctx'], cwd=tmp)
            self.assertEqual(code, 0, err)
            if not borrowed:
                text = (d / 'program.c').read_text()
                main = text[text.index('\n// main\n'):]
                main = main[:main.index('\n}\n')]
                self.assertNotIn('ctx_rec_alloc', main)
                self.assertNotIn('CTX_RECORDS', main)
                self.assertNotIn('ctx_adapt(', main)
            (d / 'account.c').write_text(wrapper)
            cc, env = toolchain.compiler()
            exe = str(d / ('records' + toolchain.EXE))
            subprocess.run([*cc, *toolchain.CFLAGS, '-I', toolchain.RT, str(d / 'program.c'),
                            os.path.join(toolchain.RT, 'ctxrt.c'), str(d / 'account.c'), '-lm', '-o', exe,
                            *toolchain.stack_flags()], check=True, env=env, capture_output=True)
            result = subprocess.run([exe], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_kotor_copy_helpers_and_table_lookup(self):
        import pathlib
        repo = pathlib.Path(ROOT).parent
        object_source = (repo / 'kotor/lib/engine/object.ctx').read_text()
        helpers = []
        for name in ('copy_bytes', 'copy_lower'):
            start = object_source.index('    fn ' + name + ' ')
            end = object_source.index('\n    }', start) + len('\n    }')
            helpers.append(object_source[start:end])
        files = ['kotor/lib/base/' + name + '.ctx' for name in ('heap', 'ci', 'le', 'text')]
        files.append('kotor/lib/formats/twoda.ctx')
        sources = [( (repo / name).read_text(), name) for name in files]
        sources.append(('namespace object {\n' + '\n'.join(helpers) + '\n}', 'copies.ctx'))
        sources.append(('''
fn bytes { mut h: heap::Heap } -> ![]mut u8 {
    let buf: [3]u8 = [1, 2, 3]
    return try object::copy_bytes{ heap = &h, s = buf[..] }
}
fn lower { mut h: heap::Heap } -> ![]mut u8 {
    let buf: [3]u8 = [65, 66, 67]
    return try object::copy_lower{ heap = &h, s = buf[..] }
}
fn lookup { t: twoda::Table } -> ?[]u8 {
    let key: [4]u8 = [110, 97, 109, 101]
    return twoda::get_string{ t, row = 0, column = key[..] }
}
fn main {} {}
''', 'kotor-probe.ctx'))
        build_sources(sources)
