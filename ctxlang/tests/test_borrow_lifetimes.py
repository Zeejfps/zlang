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
        import pathlib
        import subprocess
        import tempfile
        import toolchain
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
        # Account for actual runtime calloc/free calls, without a production metrics API.
        wrapper = r'''
#include <stdlib.h>
#include <stdio.h>
static void *live[20000];
static size_t total, count;
void *tracked_calloc(size_t a, size_t b) {
    void *p = calloc(a, b);
    if (p) { if (count == 20000) abort(); live[count++] = p; total++; }
    return p;
}
void tracked_free(void *p) {
    for (size_t i = 0; i < count; i++) {
        if (live[i] == p) { live[i] = live[--count]; break; }
    }
    free(p);
}
static void check(void) {
    if (count != 0 || total < 15000) {
        fprintf(stderr, "live=%zu total=%zu\n", count, total);
        abort();
    }
}
__attribute__((constructor)) static void install(void) { atexit(check); }
'''
        with tempfile.TemporaryDirectory(dir=toolchain.CACHE) as tmp:
            d = pathlib.Path(tmp)
            (d / 'main.ctx').write_text(source)
            code, err = toolchain.ctxc_build(toolchain.native_ctxc(), str(d / 'program.c'), ['main.ctx'], cwd=tmp)
            self.assertEqual(code, 0, err)
            (d / 'account.c').write_text(wrapper)
            cc, env = toolchain.compiler()
            rt = os.path.join(toolchain.RT, 'ctxrt.c')
            subprocess.run([*cc, *toolchain.CFLAGS, '-Dcalloc=tracked_calloc', '-Dfree=tracked_free',
                            '-c', rt, '-o', str(d / 'rt.o')], check=True, env=env, capture_output=True)
            exe = str(d / ('records' + toolchain.EXE))
            subprocess.run([*cc, *toolchain.CFLAGS, '-I', toolchain.RT, str(d / 'program.c'),
                            str(d / 'rt.o'), str(d / 'account.c'), '-lm', '-o', exe,
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
