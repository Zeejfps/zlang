# ctxlang: spec draft

Examples: [examples/list.ctx](../examples/list.ctx) (lists, allocators, bound functions), [examples/wordcount.ctx](../examples/wordcount.ctx) (files, arguments, maps), [examples/json](../examples/json) (a JSON parser and printer, as a program of several files: `ctxc run examples/json -- FILE`), [examples/glfw](../examples/glfw) (a build program, §19, and a binding of a C library, §18: `ctxc run examples/glfw`), [examples/sdl](../examples/sdl) (SDL2's events through an extern union, §12), [examples/gen](../examples/gen) (a build program that generates part of its executable with a library of its own, from the executable's own declarations too, §19: `ctxc run examples/gen`).

## 1. Top level

1. A program is a sequence of declarations: `fn`, `extern fn` (§18), `struct`, `union`, `enum`, `type`, `const`, `capability` (§15), `error` (§8, Errors), `namespace`. Any declaration may have attributes (§18).
2. There is no mutable state at top level. Top-level names may be referenced from anywhere.
3. All effects (IO, memory, OS) reach a function only through its context.
4. Source files are UTF-8. Names are ASCII: a letter or `_`, then letters, digits and `_`, and not a keyword: `fn` `struct` `union` `enum` `type` `const` `namespace` `let` `mut` `if` `else` `while` `for` `break` `continue` `match` `return` `defer` `and` `or` `not` `true` `false` `null` `extern` `capability` `ifnull` `iferr` `ifoverflow` `try`. A keyword where a name belongs is an error that says so: ``expected a name, found 'for': `for` is a keyword and can't be a name; use another, such as `for_` ``. Some words are keywords in one place only, and names everywhere else: `is` after an expression (§8, Is, rule 9), `distinct` after `type Name =` (§12, Distinct types), `in` and `at` in a `for`'s head (§11, For), `error` before a name where a declaration begins (§8, Errors), `static` before a capability's field (§15), and `expose` before a string where a declaration begins at the top of an `api.ctx` (§10, Re-exports). Other characters may appear only in comments, which are `// to the end of the line` and `/* ... */` (not nested). String and character literals are ASCII too (§11 Literals).

## 2. Functions and contexts

```text
fn name(Generics) { field: T, mut field: T, ... } -> R { body }
```

1. The `{ ... }` after the name is the **context**. It is the function's only input.
2. A context field is read-only unless marked `mut`.
3. A function can't assign to a read-only field or any field or element of it. Memory reached through a pointer inside it is not part of it (§12, Pointers).
4. `-> R` may be omitted. The function then returns no value.
5. Two fields in one context can't share a name.
6. A `mut x: T` field holds a `*mut T`. Inside the function, `x` is the place of type `T` it points to, and `&x` gives the `*mut T`.
7. A context field may have attributes, on the lines before it (§18).

## 3. Calls

```text
f{ a = expr, b = &place, c, &d, &g.e, g.h, .. }
```

1. A call is an expression of function type followed by `{ ... }`.
2. Every context field of the callee must be supplied exactly once. Order doesn't matter.
3. A read-only field of type `T` takes an expression of type `T`.
4. A `mut` field of type `T` takes an expression of type `*mut T`. If the argument has the form `&p`, `p` must be a mutable place and §3.1 applies. Any other `*mut T` expression is accepted unchecked. For a capability `T`, a pointer to one that includes it is accepted too (§15, rule 10).
5. Places and mutable places are defined in §11.
6. Punning: `c` means `c = c`, and `&d` means `d = &d`. A place (§11) that ends in a field's name is a pun of that name: `&g.e` means `e = &g.e`, and `g.h` means `h = g.h`. The place starts at a name, and may go through fields, indexes and derefs on the way (`&ws[i].g.rng`, `&q.*.rng`); only its last step counts, so `s.len` supplies `len`. Anything else without `name =` names no field, and is an error that says to write the name: an item that ends in an index (`&g.xs[i]`), a deref (`g.p.*`) or a range, a call or a literal (`g.make{}`, `make{}.h`), a `::` path (`gl::LINEAR`), or an operator's expression (`g.h + 1`). A pun whose name is no field of the callee is an error that says what to write, from the fields nothing supplies yet, or lists the fields if all are supplied. A pun is checked as the item it means (rule 10, §3.1).
7. Forwarding: a trailing `..` supplies each remaining field `F` from the local or context field named `F`. In a struct's literal it takes fields from their defaults instead (§7, rule 4). Namespace and top-level names are not considered. It supplies `F = F` for a read-only field and `F = &F` for a `mut` field. It is an error if `F` isn't in scope, or if `F` is `mut` and the name isn't a mutable place.
8. `..`, when present, must be the last item.
9. A call's result is discarded only with `_ = f{ ... }` (§11, rule 6): a call statement must return nothing.
10. **Argument order.** The items of one call or literal may be written in any order (rule 2) and are evaluated in the order they are written, so no item may change a place that another item reads or changes while they are evaluated: the result would depend on the order the fields are written in. That is a compile error, which names both items and the place. Computing one of them in a `let` before the call says which comes first.
    - An item **changes** a place `p` if, while it is evaluated, it calls a function that is given `&p`, or `&` of a place within `p`, for a `mut` field and changes that part; calls a bound function that holds `p` (§3.1), or a function it gives one to; assigns `p` in a block; or gives `&p`, or a view of an array `p`, to a function that writes through a pointer or a slice.
    - It **reads** `p` if its value depends on `p`'s: it uses `p`, or gives it read-only to a function that reads it. The call's own callee reads what it is given read-only in the same way.
    - What a function reads and changes of its fields is what its body does, through the functions it calls. A function value, an extern fn or a capability's field may read and change all of what it is given.
    - Places are compared field by field, as §3.1 compares them: changing `s.n` doesn't conflict with reading `s.m`. Places through a pointer or a slice aren't checked (§3.1, rule 6).
    - A `&p` the call itself takes for a `mut` field is neither a read nor a change: the callee gets the place, as it is when the callee runs. Nor is a bound function the call is given: it runs only when it is called.

<!-- context:
struct S { n: i32, m: i32 }
struct Vec3 { x: f64, y: f64, z: f64 }
fn bump { mut s: S } -> i32 {
    s.n = s.n + 1
    return s.n
}
fn show { n: i32, z: i32 } { _ = n + z }
fn rand { mut rng: u64 } -> f64 {
    rng = rng + 1
    return 0.5
}
fn main {} {
    let mut s = S{ n = 0, m = 0 }
    let mut rng: u64 = 1
    let mut v = Vec3{ x = 0.0, y = 0.0, z = 0.0 }
    ...
}
-->
```ctx
show{ n = s.n, z = bump{ &s } }     // error: `n` reads `s.n`, which `z` changes, in one call: ...
let z = bump{ &s }                  // the change first,
show{ n = s.n, z }                  // then the read: n sees it
show{ n = s.m, z = bump{ &s } }     // fine: bump changes only s.n
v = Vec3{ x = rand{ &rng }, y = rand{ &rng }, z = 0.0 }   // error: `x` and `y` both change `rng` in one literal: ...
```

### 3.1 Exclusivity

1. Only places (§11) that don't go through a deref are checked. Their root is a local, context field or match binding.
2. Two places **overlap** if one's steps are a prefix of the other's, with the same root. Any two `[index]` steps count as equal.
3. A call's **mut references** are each place `p` supplied as `&p` to a `mut` field, each place `p` held as `&p` by a bound-function argument, and each place held by the bound function that is called.
   - A bind holds every place it takes as `&p`, plus every place held by its `&fn` arguments, and by the bound function it binds further.
   - A `&fn` local holds every place held by any bind assigned to it.
   - A `&fn` context field holds no checked places.
4. Two mut references of one call must not overlap, except as rule 8 allows. A violation is a compile error. The places one bound function holds are checked where it is bound, not again where it is passed.
5. If a read-only field's argument is a place that overlaps a mut reference of the same call, it is passed by copy.
6. Pointers that don't come from `&p` in the call itself are not checked, and neither are places that go through a deref, a capability's static among them (§15, rule 13), nor capabilities, which never change (§15, rule 8): `os::pipe_read{ &proc, cancel = &proc, ... }` passes one twice.
7. A task's bind holds its places past the call that starts it, until the task is waited on (§15, Tasks, rules 7 to 9).
8. **Split borrows.** A call or a bind of a function declared with a body may be given mut references that overlap, where the function uses them apart: what it does through one of the two fields must not overlap what it changes through the other. So a function may be given a struct and one of its parts, `f{ &e, xs = &e.list }`, if it leaves `e.list` alone through `e`, or only reads it through both.
   - What a function **does through a field** is what its body does with the field's place, and what the functions it calls do with what it gives them of it, as for argument order (§3, rule 10): it reads a place, changes it, or gives out its address. Places are compared as rule 2 compares them, from the place the call gives for the field: with `xs = &e.list`, the function's `xs.len` is `e.list.len`. ctxc keeps three steps of each path a function uses: a deeper place counts as the one three steps down, `e.a.b.c.d` as `e.a.b.c`, here and for argument order.
   - An address is **given out** when the function returns `&p` or a view of an array `p`, stores it, or gives it to a function that doesn't use it at once. What holds it may use it later, so it counts as reading `p`, and, for a `*mut` or a `[]mut`, as changing it.
   - A function value, an extern fn or a capability's field may read and change all of what the function gives it (§3, rule 10).
   - A place a bound-function argument holds counts as changed, all of it, whenever the callee runs. A bound function beside a `&p` is allowed where the callee does nothing through the `&p`'s field that overlaps what the bound function holds: `step{ &w, note = log{ l = &w.log, _ } }`, if `step` leaves `w.log` alone. Two bound functions that hold overlapping places are an error.
   - The callee must be the function itself, named: a call through a function value, a `&fn` or a capability's field, and a call of an extern fn, have no body to look at, and must not be given overlapping references.
   - The error names the two accesses that meet: the function, what it does to which place, through which of its fields, and where: the access itself, or the call in the function's body that leads to it, with the function that makes the access. A call's being allowed depends here on the callee's body and those of the functions it calls, so a change there can make the call an error: the message points at the access that did.
   - Not allowed: a bound function beside a `&p` of a place it holds, which the callee uses too, as in `tick{ &world, engine }` with `engine` bound to `&world`. The bound function may run whenever the callee calls it, whatever the callee holds of `p` by then, such as a slice of a list that the bound function goes on to grow, and pointers aren't followed (rule 6). Bind where the function is called instead, in a call that isn't given the place: `run{ &vm, engine = call{ &world, _ } }`.
   - Not compared: memory reached through a pointer or a slice that the places hold (rule 6; §2, rule 3). Two references whose places hold the same slice both reach its elements, as two copies of a slice always do; what is compared is the slice itself, so a function that grows a list through one field and reads its items through the other is an error.

<!-- context:
struct List { len: usize }
fn push { mut list: List } { list.len = list.len + 1 }
fn main {} {
    let mut e = E{ n = 0, list = List{ len = 0 } }
    grow{ &e }
}
-->
```ctx
struct E { n: i32, list: List }
fn add { mut e: E, mut xs: List } {
    e.n = e.n + 1                   // through e: e.n
    push{ list = &xs }              // through xs: e.list
}
fn reset { mut e: E, mut xs: List } {
    e.list.len = 0                  // through e: e.list.len
    push{ list = &xs }
}

fn grow { mut e: E } {
    add{ &e, xs = &e.list }         // fine: add uses e.list through xs only
    reset{ &e, xs = &e.list }       // error: two mut references to `e` in one call: `reset` changes `e.list.len` through its field `e` ...
}
```

## 4. Binding

```text
f{ a = expr, _ }
```

1. A trailing `_` makes the call a **bind**. It produces a function value whose context is the callee's context minus the supplied fields.
2. `_` and `..` can't appear in the same call.
3. The result is a **bound function** of type `&fn{C} -> R` (see §6).
4. A read-only argument is evaluated and copied when the bind executes. A `mut` argument stores its pointer. §3.1 applies to a bind as to a call.

## 5. Function types

```text
fn{ field: T, mut field: T, ... } -> R      // unbound: a plain function
&fn{ field: T, mut field: T, ... } -> R     // bound: may hold addresses of places (§6)
```

1. A top-level `fn` has type `fn{C} -> R`. A bind (§4) has type `&fn{C} -> R`.
2. A value of type `fn{C} -> R` converts implicitly to `&fn{C} -> R`. There is no conversion the other way.
3. Both types are called the same way.

A function `g` of type `fn{Cg} -> Rg` (or `&fn`) is accepted where `fn{Cs} -> Rs` (or `&fn`, per rule 2) is expected iff:

1. `Rg` is identical to `Rs`, or `Rg` is a `!T` that fails with an error set (a function's, §8, Errors, rules 5 and 14) and `Rs` is a `!T` of an identical `T` that may fail with any error, or that declares a set holding `Rg`'s errors (§8, Errors, rule 14), and
2. for every field `n: T` in `Cg`, `Cs` has a field `n` with an identical type `T`, and
3. if the field `n` is `mut` in `Cg`, it is `mut` in `Cs`.

`Cs` may have fields that `Cg` lacks. Those fields are dropped when the value is called. A field read-only in `Cg` may be `mut` in `Cs`: a call through the converted value passes a `*mut T` for it (§2, rule 6), and the value reads the field through that pointer when it is called and passes `g` the value it read, as any read-only argument is passed (§14, rule 6): `g` sees that value, whatever the call's other arguments point to. A result of the second kind in rule 1 is **widened**: when `g` fails, the value's error is the same error, with its payload, in the numbering of `Rs`'s set: any error's, or the declared set's (§8, Errors, rule 13). All of these happen in one step: calling the converted value calls `g` once with the fields it takes, read through their pointers where they are `mut` in `Cs`, and widens what it returns. It is implicit wherever widening is (§11, Widening, rule 1), the `T` of an implicit `T` to `?T` conversion included.

<!-- context:
namespace parse {
    error empty
    error bad_digit{ at: usize }
}
fn main {} {
    _ = run{ s = "12" }
}
...
-->
```ctx
fn number { s: []u8 } -> !u64 {                  // fails with number's set, inferred
    if s.len == 0 { return parse::empty }
    let mut n: u64 = 0
    for c at i in s {
        if c < '0' or c > '9' { return parse::bad_digit{ at = i } }
        n = n * 10 + @as(u64, c - '0')
    }
    return n
}
fn word { s: []u8 } -> !u64 { return @as(u64, s.len) }

// Each converts to the table's type, whose `!T` may fail with any error.
fn parse_with { table: []fn{ s: []u8 } -> !u64, kind: u8, s: []u8 } -> !u64 {
    return table[kind]{ s }
}

fn run { s: []u8 } -> u64 {
    let parsers: [2]fn{ s: []u8 } -> !u64 = [number, word]
    match parse_with{ table = parsers[..], kind = 0, s } {
        ok{ value } => { return value }
        err{ error } => {
            match error {
                parse::bad_digit{ at } => { return at }     // number's error, with its payload
                else => { return 0 }                       // any error: `else` is needed (§8, Errors, rule 10)
            }
        }
    }
}
```

A function that only reads a field is accepted where the field is `mut`:

<!-- context:
fn main {} {}
-->
```ctx
fn show { mut io: Io, a: i64 } { _ = @fmt(&io, "{} ", a) }
fn each { mut a: i64, f: &fn{ mut a: i64 } } { f{ &a } }

fn show_x { mut io: Io, mut x: i64 } {
    each{ a = &x, f = show{ &io, _ } }      // show only reads `a`: it gets the i64 `&x` points to
}
```

## 6. Bound functions

1. `&fn{C} -> R` may only be the type of a local or of a read-only context field. It can't be a return type, a struct field type, a union payload type, an array element type, the `T` of `?T` or `*T`, or the type of a `mut` context field. A value whose inferred type holds one is an error as well: `&f`, `[f]`, or an `if` whose branches give `f` and `null`.
2. A bound function can't be assigned to a local declared in a scope outside that of any place it holds (§3.1.3, including places held through nested binds).
3. A bound function may be stored in a local and passed as a call argument. Its capture record lives until the invocation that creates it returns, after its deferred statements, on both normal returns and `try` returns. A later execution of the same bind never changes what an earlier one's value, if it can still be called, calls with: in a loop, each keeps what it captured. Whether two executions share memory can't be seen, so the compiler reuses a record's memory where no earlier value can still be called. A never-returning invocation that keeps records it can still call keeps their memory; records are not reclaimed at their last use.
4. Code that only calls a function value should take `&fn`, which accepts both kinds. Code that stores one must take `fn`, which rejects bound functions.

## 7. Structs

```text
struct Name(Generics) { field: T, field: T = e, ... }
Name{ field = expr, field, ... }
Name{ field = expr, .. }
```

1. A struct literal supplies every field exactly once, except those its `..` takes from their defaults (rule 4). Punning works as in calls.
2. A field may have type `fn{C} -> R` but not `&fn{C} -> R` (§6).
3. A field may have attributes, on the lines before it (§18), as a variant's payload's and an error's may.
4. A field may have a **default**, `field: T = e`: a const (§14) of type `T`, computed while compiling, whose names resolve in the struct's namespace, as a const declared beside it would; it can't name the struct's other fields. A literal ending in `..` takes each field it doesn't supply from its default; it must still supply every field without one, and without `..` it supplies every field, defaults or not. `..` in the literal of a struct without defaults is an error. A field whose type names one of the struct's generic parameters can't have a default, nor can a field of an extern union, a union variant's payload or an error.
5. Defaults are for literals only: a struct's zero value (§11, Initialization), which a `let` without an initializer, a static and allocated memory start as, is every field zero, defaults or not.

## 8. Unions

```text
union Name(Generics) {
    variant{ field: T, ... },
    variant,
}
```

1. Unions are tagged. A value holds exactly one variant.
2. A variant has a payload (a list of named fields) or no payload.
3. Construction: `Name::variant{ field = expr, ... }` or `Name::variant`. Every payload field must be supplied exactly once. Punning works as in calls.

### Match

```text
match e {
    variant{ f, g }           => { ... }
    variant                   => { ... }
    a{ x = n } | b{ y = n }   => { ... }
    else                      => { ... }
}
let name = match k { a => "A", b => "B" }       // arms without braces
```

1. The scrutinee is a union, a `?T`, an enum (§12, Enums) or an integer (below). The arms must be exhaustive. `else` matches every variant not listed, and must come last. `else` is an error if every variant is already listed.
2. Each variant appears in at most one arm, and at most once in it.
3. An arm may list several patterns separated by `|`; its body runs for any of them. Every pattern must bind the same names, and each name must have the same type and be bound the same way (with or without `&`) in all of them. `else` can't be combined with other patterns.
4. A pattern `variant{ f }` binds payload field `f` as a read-only local. `variant{ f = x }` binds it under the name `x` instead. A pattern may bind a subset of the fields.
5. If the scrutinee has type `*U` or `*mut U` for a union `U`, the match goes through the pointer. In its arms, `&f` binds payload field `f` as a place, and `&f = x` binds it as `x`. The place is mutable only through a `*mut U`.
6. `&f` in a pattern is an error unless the scrutinee is a pointer.
7. If the scrutinee is `&p`, no place that overlaps `p` (§3.1) may be accessed inside an arm except through that arm's bindings. For other pointer scrutinees this isn't checked.
8. `match` is a statement, and can also be an expression (§11, If and match expressions).
9. To take one variant apart and leave on any other, use `let` with a pattern (§11, Let-else). To test for one, use `is` (§8, Is).
10. A union's zero value is its first variant, with every payload field zero, if those fields all have zero values (§11, Initialization).
11. An arm's body is a block, or one statement without braces, which is a block of that statement alone: an expression, the arm's value (`a => "A"`), or a call, an assignment, a `return`, `break` or `continue`, an `if`, or any other statement but a `let` and a `defer`, which would do nothing there and need the block. An arm without braces ends where its statement does, at the end of its line, or at a `,` or the match's `}`; a `,` may follow any arm. Its expression goes on to the next line as any does (§11, rule 3), except to a line that starts with `-` and an integer literal before `=>`, `|` or `..=`: that is the next arm's pattern, as in `0 => "zero"` followed by `-1 => "minus one"`.

### Match on integers

<!-- context:
const OP_ADD: u8 = 1
const OP_SUB: u8 = 2
namespace gl { const TRIANGLES: u32 = 4 }
fn main {} {
    let op: i32 = 0
    let c: u8 = '7'
    ...
}
-->
```ctx
match op {
    0 => {}
    OP_ADD | OP_SUB => {}               // folded consts (§14)
    gl::TRIANGLES => {}
    'a'..='z' | '_' => {}               // a range includes both ends
    -8..=-1 => {}
    else => {}
}
if c is '0'..='9' {}
```

1. A scrutinee of an integer type (`i8`..`i64`, `u8`..`u64`, `usize`) is matched by value. Its patterns are integer literals (a character literal is one), with a `-` or not; names of consts, with their path, whose values are folded (§14, rule 1); and ranges `lo..=hi` of these, which include `lo` and `hi`. `lo..hi` is a syntax error.
2. Each value must convert to the scrutinee's type as an argument would (§11, Widening and Literals): `300` doesn't fit a `u8`, and neither does an `i32` const whose value is 300, while one whose value is 3 converts (§11, Widening, rule 7).
3. No value may be matched by two patterns, in one arm or two, and a range's `lo` can't be above its `hi`.
4. `else` is required, even if the patterns cover every value. Patterns have no bindings.
5. A pointer to an integer is an error: match on `p.*`. Let-else doesn't apply to integers.
6. `e is P | Q` tests an integer the same way (§8, Is), and binds nothing.

### Optional

1. `?T` is a built-in union with variants `null` and `some{ value: T }`.
2. `null` is a value of every `?T`. An expression of type `T` converts implicitly to `?T` as `some{ value = expr }`.
3. Narrowing: where an `x` of type `?T` is known not to be null, it has type `T`. `x` must be a `let` local or a read-only context field, or a path of struct fields from one, such as `v.a.b` (not through a pointer, `.*` or an index). A mutable one doesn't narrow, since a write between the test and a use could make it null. Unwrap it into a new local instead, which holds the value the test saw: `if let v = x { ... }` (§11, If let), `let v = x ifnull { return }` (rule 7), or `x is some{ value = v }` (§8, Is) in a condition that combines tests. Where one of these places is used as its `T`, the error says so, as it does where a narrowed `x` is tested as an optional (`ifnull`, `if let`, `is some`), though it has a value there.
4. A condition narrows some `x`s when it is true and some when it is false:
   - `x != null` narrows `x` when true; `x == null` narrows `x` when false.
   - `x == v`, for a `v` whose type isn't optional, narrows `x` when true, and `x != v` narrows `x` when false (§11, Expressions, rule 5). So does `v == x`.
   - `x is P` narrows `x` when true, unless `P` lists `null`: then it narrows `x` when false, as `x == null` does (§8, Is).
   - `not c` swaps what `c` narrows when true and when false.
   - `a and b` narrows, when true, what `a` or `b` narrows when true; when false, what both narrow when false.
   - `a or b` narrows, when true, what both narrow when true; when false, what `a` or `b` narrows when false.
   - Any other condition narrows nothing.
5. Where narrowing holds:
   - In `a and b`, what `a` narrows when true holds in `b`. In `a or b`, what `a` narrows when false holds in `b`.
   - In `if c { B1 } else { B2 }`, what `c` narrows when true holds in `B1`, and when false in `B2`. In `while c { B }`, what `c` narrows when true holds in `B`.
   - After an `if` statement: if one branch always leaves (it ends a path, §11.7, 8, 9), the other branch's narrowing holds from after the `if` to the end of the enclosing block. Without an `else`, that is what `c` narrows when false, if the `{ }` leaves. A `let x` in that same block is an error if `x` was declared there, and shadows it otherwise.
   - After a `@require(t, c)` statement (§13, Checks, rule 7): what `c` narrows when true holds from after it to the end of the enclosing block, as after `if not c { return }`, since a test doesn't go on from a `@require` that doesn't hold.
6. Representation: `?*T` and `?*mut T` are a pointer, the size of one, with `null` the address 0. A pointer is never null (§12), so no tag is needed, and the layout is C's nullable pointer, which is what lets one cross into C (§18). So are `?extern fn{C} -> R` (§12) and `?c::String` (§18), whose pointer is never null either. Every other `?T`, `??*T` included, holds a tag and its payload.
7. `e ifnull x`, for `e` of type `?T`, is `e`'s value if it has one, and otherwise `x`, which is evaluated only then. `x` is an expression, or a block that gives a value or leaves, as a branch of an `if` expression does (§11, If and match expressions): `f{} ifnull { return 1 }`. It is the expression `match e { some{ value } => { value } null => { x } }`, and its type is that match's: `T` when `x` converts to `T`, and `?T` when `x` is a `?T` (or `null`). An `x` that is an expression takes every handler after it, so `a ifnull b ifnull 0` tries `a`, then `b` (§11, Expressions, rule 7). It is an error if `e` isn't an optional; a narrowed `x` (rule 3) isn't one.

<!-- context:
struct Obj { name: ?utf8::String }
fn hex_digit { c: u8 } -> ?u32 {
    if c >= '0' and c <= '9' { return @as(u32, c - '0') }
    return null
}
fn print { s: utf8::String } {}
fn value { c: u8, o: ?Obj, s: utf8::String, m: map::Map(u32, u32, arena::Arena), key: u32 } -> ?u32 {
    let mut v: u32 = 0
    ...
    return v
}
fn main {} {}
-->
```ctx
let d = hex_digit{ c }            // ?u32
if d == null { return null }
v = v * 16 + d                    // d: u32

if o == null or o.name == null { return null }
print{ s = o.name }               // o: Obj, o.name: utf8::String

let n = utf8::parse_i64{ s } ifnull 0              // i64
let e = map::get{ m, key } ifnull { return null }   // leaves when the key is missing
```

### Is

<!-- context:
union Ref { local{ var: u32 }, constant, variant, enumval }
union Cut { some{ to: usize }, slice{ to: usize }, none }
enum Kind: u8 { field, method }
fn use { var: u32 } {}
fn take { r: Ref } {}
fn test { mut fs: Fs, path: []u8, mode: fs::Mode, r: ?Ref, c: Cut, m: map::Map(u32, Kind, arena::Arena), key: u32 } {
    ...
}
fn main {} {}
-->
```ctx
if r is local{ var } { use{ var } }             // r: ?Ref, for a union Ref
if fs::remove{ &fs, path } is ok {}             // a !T: ok, err or errors
if fs::open{ &fs, path, mode } is fs::not_found | fs::is_directory {}
if r is constant | variant | enumval {}
if c is some{ to } | slice{ to } { _ = to }     // both bind `to`, of one type
if r is local { take{ r } }                     // r: Ref here
let found = map::get{ m, key } is field         // ?Kind for an enum Kind: null doesn't match
if not (r is local{ var }) { return }           // var is bound from here to the end of the block
use{ var }
```

1. `e is P` is a `bool`: true when `e` holds `P`'s variant. `P` is a pattern as in a match arm (§8, Match), its variant named alone, or several separated by `|`: then it is true for any of them, and each must bind the same names, each with the same type, as an arm's patterns do (§8, Match, rule 3). A binding is read-only: `&f` is an error.
2. `e` is a union, an enum, a `?T`, an integer (§8, Match on integers), a `!T` or an error. A pointer is an error.
3. On a `!T`, `P` is `ok`, `err` (each with its binding or not, `ok{ value = v }`) or errors, and on an error, errors. An error is named as in a match arm, with its path (`fs::not_found`), and binds its payload's fields. `P` can't list `ok` or `err` with errors. Each error listed must be one `e` can be, which is checked once the sets are inferred, as for a match (§8, Errors, rule 10), but unlike a match's they needn't be all of them. `e`'s error isn't passed up: it is tested, and dropped.
4. On a `?U` for a union or enum `U`, a pattern may name a variant of `U`, which null doesn't match. `null` and `some` still name the optional's own variants. `match` doesn't do this: it lists exactly its scrutinee's variants.
5. Its bindings are bound where the test is known true. `e is P` binds them when true, and `not`, `and` and `or` combine what conditions bind as they combine what they narrow (§8, Optional, rule 4). A name that would be bound twice, as in `a is x{ v } and b is y{ v }`, isn't bound, and neither is one that only one side of an `or` binds.
6. They are in scope where narrowing would hold (§8, Optional, rule 5): in `b` of `a and b`, in the first branch of `if c` and the body of `while c`, and after an `if` whose branch leaves when `c` is false, or a `@require` of `c` (§13, Checks, rule 7). After either, they are declared in the enclosing block as a let-else's bindings are (§11, Let-else): a later `let` of the same name in that block is an error.
7. `x is P`, for an `x` of type `?T` that can narrow (§8, Optional, rule 3), narrows `x` to `T` where it is known true, for a `P` that doesn't list `null`: `if r is local { take{ r } }`. A `P` that lists `null`, as `x is null` does, narrows `x` where the test is known false, as `x == null` does. This is the narrowing of §8, Optional, so it combines with `and`, `or` and `not` and holds where any narrowing would. A `let mut` local or a mutable field doesn't narrow, but its pattern's bindings still bind: `w.tlk is some{ value = t }` gives a `t` of type `T` either way. Alone in an `if`, that is `if let t = w.tlk` (§11, If let).
8. `is` binds at the level of `==` and doesn't chain with comparisons (§11, Expressions). `not e is P` is `not (e is P)`, and `a is x and b is y` needs no parentheses.
9. `is` is the operator only after an expression, and a name anywhere else: `let is = f{}`, `fn is{ a, b }` and a field `is` are allowed, and `u is is` tests for a variant `is`. After an expression on its line it is always the operator, since no name can follow an expression there. At the start of a line it is the operator when a pattern follows it on that line (a name, `null`, or an integer literal, with a `-` or not), as a test that goes on from the line before does (§11, rule 3); before anything else it is a name that begins a statement, as `is = 1`, `is{ ... }` and `is.x = 1` do.

### Errors

<!-- context:
fn report { e: error } {}
fn main {} {
    _ = sum{ a = "1", b = "2" }
}
-->
```ctx
namespace parse {
    error empty
    error bad_digit{ at: usize }                 // an error with a payload
}

fn number { s: []u8 } -> !u64 {                  // a u64, or one of the errors its body returns
    if s.len == 0 { return parse::empty }
    let mut n: u64 = 0
    for c at i in s {
        if c < '0' or c > '9' { return parse::bad_digit{ at = i } }
        n = n * 10 + @as(u64, c - '0')
    }
    return n
}

fn pair { a: []u8, b: []u8 } -> !u64 {
    let x = try number{ s = a }                  // number's error is returned: pair's set gains number's
    let y = number{ s = b } iferr 0              // or a default
    return x + y
}

fn sum { a: []u8, b: []u8 } -> usize {
    match pair{ a, b } {
        ok{ value }  => { return @as(usize, value) }
        err{ error } => {
            report{ e = error }                  // code every error shares, once
            match error {                        // then by kind, exhaustive over pair's set
                parse::empty        => { return 0 }
                parse::bad_digit{ at } => { return at }
            }
        }
    }
}
```

1. `error name` or `error name{ field: T, ... }`, at the top level or in a namespace, declares an error: a value, named as a function is (`parse::empty`, or `empty` inside `parse`). `name` is the error, and an error with a payload is `name{ field = e, ... }`, every field supplied once, as in a literal (§7). `error` is a keyword only where a declaration begins and a name follows it. An error has no generic parameters and can't be named `ok` or `err`.
2. A payload holds any type but a `!T` or an error, pointers and views included: `error missing{ name: c::String }`. An error is passed up past frames that end, so the escape check (§14) treats it as it does any value: returning an error derived from a local, or passing one up with `try`, is an error. Whether a function's error type holds a pointer depends on its set (rule 5), so those errors are checked once the sets are inferred.
3. An error value has an **error type**: a set of errors. `error` is the type of any error, and every error type converts to it. A set is written `error(A, B, ...)`, of errors and other sets (rule 14), and may be open (rule 15); the others come from a function's result (rule 5) or from one error alone.
4. `!T` is a T or an error. `!` alone is `!T` without a value: a function returning it returns nothing or fails. In such a function, `return` without a value and reaching the end of the body return its `ok`.
5. A function's result `!T` fails with its **error set**, inferred: the errors its body returns, plus the sets of the calls whose errors it returns or passes up with `try`, repeated through recursion until no set grows. ctxc compiles the whole program, so every direct call has a body to infer from. `!T` written anywhere else, as a function type's result, a field or a local's type, may hold any error. A function, or a function type, may declare its set instead (rule 14).
6. A T converts implicitly to `!T`, as its value (§11, Widening). An error, or a `!T`, converts to an error type, or a `!U` of the same `T`, that holds its errors: the result of the function being checked, whose set gains them, or any error. A set never takes another function's errors: `r = g{}` for a local `r` of `f{}`'s type is an error.
7. `try e`, for `e` of type `!T` in a function that returns `!U`: `e`'s value, or, if `e` is an error, `return e` (deferred bodies run first). The function's set gains `e`'s errors. It is a prefix operator, at the level of `not`, and its operand ends at the `}` of its first call: `try f{}.x` is `(try f{}).x`, the field of `f{}`'s value, and `try a.b{ ... }` tries the call of `a.b`. An operand without a call is the whole postfix expression, as `try r.x` is for a field `x` that is a `!T`; for a `!T` that a call's result holds, write `try (f{}.x)`, which the error says where `f{}` isn't a `!T`. `try` is an error in a `defer`, and as a statement its operand must be a call. `try! e` is `e`'s value, or, if `e` is an error, a panic, as `@panic` (§13), at the `try!` whose reason names the error without its payload: for an error the function can't handle, such as running out of memory where that is fatal. It needs no `!U` result, adds nothing to the function's set, and is allowed in a `defer`; as a statement its operand must be a call, as with `try`.
8. `e iferr x`, for `e` of type `!T`, is `e`'s value if it isn't an error, and otherwise `x`, as `ifnull` is for `?T` (§8, Optional, rule 7): `x` is an expression, or a block that gives a value or leaves. `e iferr err{ error } { ... }` binds the error in the block, as `let ... else` does. For a bare `!` it has no value, and is a statement: `close{ &fs, file } iferr { return 1 }`. A discard's `x` may give no value, whatever `T` is (§11, rule 6): `_ = f{} iferr { log{} }`. A handler after a block's `}` takes the whole expression before it, so a `!?T` is taken apart in one expression, its error first: `let v = f{} iferr { return } ifnull { return }` (§11, Expressions, rule 7).
9. A `match` on a `!T` has the arms `ok{ value }` (`ok` for a bare `!`) and `err{ error }`, where `error` has the `!T`'s error type. `let ok{ value } = e else err{ error } { ... }` takes one apart (§11, Let-else). The arms may instead list errors next to `ok`: then `ok` must be listed, and a last `err{ error }`, or `else`, takes the errors not listed. A `match` on an error lists errors, with `else` for the rest. An arm doesn't mix `ok` or `err` with errors.
10. A listed error must be one the value can be, and without `else` or `err` every one it can be must be listed: adding an error to a function breaks the matches that listed all of its errors. With `else` or `err`, at least one must be left for it. These are checked once the sets are inferred. A value of `error`, or of a function type's `!T` that declares no set, may be any error of the program, so a match on one needs `else` or `err` (rule 15).
11. An error type or a `!T` isn't a C type (§18) and can't be held by a const (§14). Neither has a zero value. `match` doesn't go through a pointer to one.
12. A function whose result's set is inferred, or declared, is a value of a function type whose `!T`, of the same `T`, may be any error (§5), or fails with a declared set that holds its errors (rule 14): its error is widened into that set's numbering. A bind of it (§4), and a generic one's instance, convert the same way. A value called through that type fails with its set: any error, so a match on its result needs `else` or `err` (rule 10) and lists the function's errors to get them back with their payloads, or the declared set. Any error takes every set, so that conversion is allowed while the sets are still inferred, in a function that converts itself included; one into a declared set is checked once they are. A call through the value is a call (§14, Escape check): its error may hold what its read-only arguments are derived from, if any error of the program has a payload that holds a pointer. No written type names a function's inferred set: a local inferred from the function (`let g = f`) has it, as `f{}`'s result does, and takes no other function's (rule 6). Neither changes for an `extern fn`, which can't return a `!T` (§18), nor for consts, which hold no function value (§14).
13. Representation: `!T` is a tagged union of `ok{ value: T }` and `err{ error: E }`. An error type is a tagged union of its set's errors, in the order they are declared in the program, sized for the largest payload; passing an error into a larger set renumbers it. Two error types with the same errors, both open or both not, are the same type. A function value widened by §5 is a thunk the compiler writes, which calls the function and renumbers its error, copying the payload; so is one that takes a field read-only where its type has it `mut` (§5), whose thunk reads the field through its pointer, and one value that needs both gets one thunk: for a named function, or a bind of one, it calls the function directly and is no more a record than the function or the bind was; any other value it holds in a record of its own, made when the value converts. A function whose set is already every error needs no renumbering, and so no thunk unless a field it takes read-only is `mut` in the type.
14. `E!T`, or `E!` without a value, is a `!T` whose errors are set E's: `error(A, B, ...)`, whose errors are those of each of A, B, ..., each an error or a set; an alias of one (`type ParseError = error(empty, bad_digit)`); one error alone (`parse::empty!u64`); or `error`, any error. A function's result written so **declares** its set: its body may fail only with E's errors, which is checked once the sets are inferred, and every caller sees E, whatever the body returns, so a match on its result lists E's errors (rule 10). E may hold errors the body never returns: a declared set is what the function may fail with, a contract that holds however its body changes, and that several functions can share, as std's platform layers do (§17). A declared set converts to a larger one or to any error, as an inferred one does, and an inferred one joins a declared one only if each of its errors is in it. A function type may declare one too, `fn{ ... } -> E!T`: a function value converts to it if its errors are in E (an inferred set's checked once it is), its error renumbered as rule 12's are, and a call through it fails with E.
15. `error(A, B, ..)`, with `..` last, is an **open** set: it may gain errors, as one whose errors come from the platform does (§17). A match on an open set, or on a set it joined, needs `else` or `err` even when it lists every error, and that arm isn't unreachable. A set that holds an open one, `error(Open, c)`, is open, and so is a function's inferred set once an open set joins it: through `try`, a return or a writer (§13, Formatting). An open set joins only an open set, or any error: a closed set promises its errors are all there are, which an open one can't.

## 9. Generics

1. Generic parameters are types, listed in `( )` directly after a declaration's name.
2. `( )` after a name or `::` path, on the same line, is generic application: `list::new(i32)` and `list::new (i32)` mean the same. Everywhere else, `( )` groups an expression. This is unambiguous because calls use `{ }` and nothing else can follow a name with `(`. Builtins are the exception (§13).
3. At a call, struct literal or union construction, explicit arguments bind parameters left to right. The remaining parameters are inferred from the supplied fields or the expected type. A parameter that can't be inferred is an error.
4. In a literal, a generic struct or union may be named without arguments (`Slice{ ... }`), and then every parameter is inferred.
5. A function's parameter may be an **error set** instead, `E: error`: its argument is a set (§8, Errors), given (`retry(u64, net::Error)`) or inferred, as from a function value's `E!T` result. `E!T` in its signature then fails with the argument's errors, so a function that forwards a callback's `!T` gives its callers the callback's own set: `fn retry(T, E: error) { f: &fn{} -> E!T, times: u32 } -> E!T`. Its body may pass E's errors up only into E, or into any error; a set it infers itself, which serves every instance, then may be any error. E holds no error of its own, and a match on one needs `else` or `err`, as on an open set (§8, Errors, rule 15).
6. A function's body may compare, hash and order values of its parameters' types: `==` and `!=` (§11, Expressions, rule 5), `@hash` (§13, Hashing), and `<`, `<=`, `>` and `>=` (§11, Expressions, rule 1). Each one it uses is then required of the type every use of the function gives that parameter, also where the use is in another generic function and gives one of its own parameters. Nothing is written for it in the signature: the error is where the function is named, and says which function needs what, and which part of the type lacks it. Arithmetic and `@as` don't apply to a value of a parameter's type.

## 10. Namespaces

```text
namespace name { declarations }
name::item
```

1. A namespace holds only top-level declaration kinds (§1). Namespaces may nest.
2. Inside a namespace, its own items are referenced unqualified.
3. `::` resolves namespace members and union and enum variants. `.` resolves struct fields.
4. Two `namespace` declarations of one name in one scope, in one file or in several, declare one namespace: each adds its declarations to it, and inside either, the other's items are referenced unqualified. A name still can't be declared twice in it, from one file or two. A namespace nested in one of them joins the one of its name nested in the other, as `gff::inner` does below. std's namespaces and the program's are in different scopes (§17), so a program's `list` never joins std's: it shadows it.

<!-- context:
namespace gff {
    struct Gff { size: usize }
    error truncated
}
fn main {} {}
-->
```ctx
// gff/read.ctx
namespace gff {
    fn read { bytes: []u8 } -> !Gff {
        try check{ bytes }
        return Gff{ size = bytes.len }
    }
    namespace inner { fn base {} -> i64 { return 1 } }
}

// gff/write.ctx
namespace gff {
    fn check { bytes: []u8 } -> ! {             // gff::check, which read calls unqualified
        if bytes.len < 4 { return truncated }
    }
    namespace inner { fn more {} -> i64 { return base{} + 1 } }
}
```

### Name lookup

1. Names are in one of two kinds:
   - **paths:** namespaces, structs, unions, enums, type aliases
   - **values:** locals, context fields, functions, consts
2. A name is looked up only among names of the kind its position requires:
   - the name before `::` is a path
   - a name in a type is a path
   - a name in an expression is a value
3. Lookup goes from the innermost scope outward: block locals, then context fields, then enclosing namespaces, then top level. The first match of the required kind wins.
4. A path and a value may share a name in the same scope. Two paths or two values may not, except two namespaces, which are one (§10, rule 4).
5. A value in an inner scope shadows a value of the same name in an outer scope.
6. In a call or literal `f{ ... }`, a local or context field `f` that doesn't hold a function doesn't hide an outer name: lookup goes on outward for a function value, then for a path. `let binders = binders{}` calls the function `binders`. If nothing else matches, the local is the callee, and the call is an error.
7. A declaration a module hides from the code doing the lookup isn't a match (Modules, rule 2): lookup goes on to one it sees. If it sees none, naming the hidden one is an error (Modules, rule 11).

### Modules

A folder that holds a file named `api.ctx` is a **module**: code outside it names only what that file declares. Every name is public until a module hides it, so a helper one file has is there for others to call; a module draws a boundary where a contract is wanted. ctxc compiles the whole program at once, so `api.ctx` exists only as the contract, which the compiler checks both ways, as OCaml checks a `.mli`.

<!-- context:
// file: gff/read.ctx
namespace gff {
    struct Gff { header: Header, fields: []Field }
    struct Header { count: u32 }
    fn read { bytes: []u8 } -> error(bad_magic, truncated)!Gff {
        let header = try parse_header{ bytes }
        return Gff{ header, fields = slice::empty(Field){} }
    }
    fn field { g: *Gff, label: []u8 } -> ?Field { return null }
    fn parse_header { bytes: []u8 } -> !Header {
        if bytes.len < 4 { return truncated{ at = bytes.len } }
        if bytes[0] != 'G' { return bad_magic }
        return Header{ count = 0 }
    }
}
// file: gff/main.ctx
fn main {} {}
// file: gff/api.ctx
...
-->
```ctx
// lib/formats/gff/api.ctx: this folder is a module
namespace gff {
    type Gff                                         // opaque: held and passed, never looked into
    struct Field { label: []u8, kind: Kind }
    enum Kind: u8 { byte, word, dword, string }

    error bad_magic
    error truncated{ at: usize }

    fn read { bytes: []u8 } -> error(bad_magic, truncated)!Gff
    fn field { g: *Gff, label: []u8 } -> ?Field
}
```

`read.ctx` beside it defines `struct Gff`, `read` and `field` with those signatures, and `parse_header`, which isn't in the api: only the module's files call it.

1. A folder that holds a file named `api.ctx` is a module, wherever it is on disk. Its **inside** is every source file in the folder and in its subfolders, at any depth; everything else is **outside**, sibling and parent folders included. A file's place on disk decides which modules it is inside, not the build that adds it (§19, rule 5), and a module whose `api.ctx` isn't one of the program's files is an error at the first of its files that is. A file a build program generates is in its executable's root (§19, rule 13). A program of one file (`ctxc run file.ctx`) is in no module.
2. Code inside a module sees every declaration in it. Code outside sees only what its `api.ctx` declares, and what that file re-exports of the modules nested in it (Re-exports). A module nested in another is inside it: what its api declares is visible inside its parent module, or everywhere if it is in none. Namespaces are never hidden, only what they hold.
3. `api.ctx` is ctxlang: namespace blocks and declarations, and the one file where a fn has no body and a type may have no `= T`. No keyword marks it: its name does. A declaration that is complete without a body is declared in `api.ctx` alone, and the inside uses it: an `error`, an `enum`, a `struct` with its fields, a `union`, a `const`, a `type` alias, an `extern fn`, and a `capability` with function fields only. Three have a second half in the module's files, with the same name in the same namespace:
   - `fn name(G) { ... } -> R` without a body declares a fn that the inside defines with exactly that signature: its generic parameters, its context fields in their order with their `mut`, and its result. The definition may write `!T` where the api writes `E!T`, if the errors its body fails with are E's.
   - `type Name(G)` without `= T` declares an **opaque** type that the inside defines as a struct, a union or an enum. Outside, it is held, copied, passed, returned, compared with `==` and given its zero value (§11, Initialization), but not made with a literal or `@as`, and its fields and variants aren't named, matched on or tested with `is`. ctxc compiles the whole program, so its size is known, and it is passed by value as any type is.
   - `capability Name`, or one with its function fields alone, declares a capability whose `static` and `extern` fields (§15, rules 12 and 13) the inside adds, in a declaration of the capability that repeats every field the api's has.

   Each half without the other is an error, and so is a definition that doesn't match: its error says how. A fn in `api.ctx` with a body is one error, and the rest is checked as if it had none; one without a body, or `type Name`, anywhere else is one error.
4. **Nothing leaks through a signature.** A type or an error that a declaration in `api.ctx` names, in a fn's signature, a struct's fields, a union's payloads, an alias or a set, is in the api too, in full or opaque: an error names each one that isn't.
5. **A fn in `api.ctx` says which errors it fails with.** Its result is `E!T` (§8, Errors, rule 14), never `!T`, so every caller reads what it fails with, and the inside can't add an error without changing the contract. Inside the module, results are inferred as before. The error writes the set the body is inferred to fail with, and `ctxc check --fix` writes it. A `#write` fn's result is a bare `!` (§13, Formatting, rule 4): its errors are its sink's.
6. A fn half carries the attributes that tell callers how it is used, `#task`, `#write` and `#convert`, and its definition has the same; the definition has the rest. No `#test` fn is in `api.ctx`.
7. A `#test` fn sees what any code in its file sees (§20). One inside the module, in a subfolder kept for tests included, tests it as a white box; one outside tests it through its api. A test that needs a hidden name shows that the name is part of the contract, and goes in `api.ctx`, or is a module of its own nested inside, with an api the tests use.
8. **A module's state is in a capability whose statics only it reaches.** A static or a C variable is reached, and a capability with fields is made with a literal, only in a function declared directly in the capability's namespace and inside the module that declares it (§15, rules 6, 12 and 13), so another module that adds to the namespace doesn't reach it. The api declares the capability without its statics, and the inside with them; a capability whose fields are statics alone is one without fields (§15, rule 1), which `main` receives and passes down as it passes an `Io`.
9. **A hidden name is in its module's scope, not its namespace's.** Two declarations of a name clash only where both are visible: a hidden `gff::put_row` in one module and a hidden `gff::put_row` in another are two functions, and code inside either sees its own. One that clashes with a declaration visible where it is declared is an error, as two declarations of a name are (§10, rule 4).
10. Namespaces and folders are separate. A module may declare several namespaces in `api.ctx`, and several modules may add to one namespace. `ctxc where` says which module and file declare a name (§19, rule 10).
11. Naming what a module hides is an error that names the boundary: ``gff::parse_header` is inside module `lib/formats/gff`, whose api.ctx doesn't declare it``. A `#convert` or `#write` fn is a name too: a literal or an `@fmt` sees only those its code could name (§18, Literal conversions, rule 4; §13, Formatting, rule 4).
12. Privacy is of names, not values. A function value the inside hands out (§5) is called by whoever holds it.

<!-- context:
// file: build.ctx
fn build { mut b: Build } {
    let exe = build::exe{ &b, name = "tool", root = "." }
    build::add_sources{ &b, exe, dir = "gff" }
}
// file: gff/api.ctx
namespace gff {
    type Gff
    error bad_magic
    fn read { bytes: []u8 } -> error(bad_magic)!Gff
}
// file: gff/read.ctx
namespace gff {
    struct Gff { size: usize }
    fn read { bytes: []u8 } -> error(bad_magic)!Gff {
        if bytes.len == 0 { return bad_magic }
        return Gff{ size = bytes.len }
    }
    fn parse_header { bytes: []u8 } -> usize { return bytes.len }
}
// file: main.ctx
...
-->
```ctx
fn main {} -> i32 {
    let g = gff::read{ bytes = "GFF" } iferr { return 1 }
    let n = g.size                                   // error: gff::Gff is opaque outside module ...
    return @as(i32, gff::parse_header{ bytes = "x" }) // error: `gff::parse_header` is inside module ...
}
```

### Re-exports

A re-export makes a name that a nested module's api declares visible past its parent's boundary. It never makes a new name: `gff::read` is `gff::read` at every level, so a name always means one thing.

```text
lib/formats/
    api.ctx              // formats is a module, for internals gff and tpc share
    shared.ctx           // inside formats: gff and tpc see it, nothing outside does
    gff/
        api.ctx
    tpc/
        api.ctx
```

1. **Restating** a declaration re-exports it. A declaration in `api.ctx` whose name a nested module's api makes visible inside this module is that declaration, not a new one. A restatement may hide a type's inside, never change a declaration: a struct, union or enum the nested api declares in full may be restated as an opaque `type Gff`, which is then opaque past this boundary and in full inside it; any other restatement matches exactly. So a name means one thing, with one type, at every level it reaches, and the outer api has the whole contract, signatures and all, in one file. A restatement can't show some of a struct's fields (code outside couldn't make one, since a literal supplies every field), hide some of an enum's or a union's variants (code outside would hold values it can't name), widen or narrow a fn's errors, or change anything else of a signature: each would give one name two meanings.
2. **`expose "path"`** re-exports all of a nested module's api, as that api declares it. The path is a string, relative to the folder of this `api.ctx`, so that a folder no ctxlang name can name (`2da`) is reached too. It names a module whose folder is in this one, directly or through folders that aren't modules. `expose` is a keyword only where a declaration begins at the top of an `api.ctx`, as `error` is only before a name (§1, rule 4).
3. **One boundary at a time.** An `api.ctx` re-exports only what code inside its module sees: a nested module's api, with what that api re-exports in turn. A name in `formats/gff/chunks/` crosses `formats` only if `gff/api.ctx` re-exports it first.
4. A module is either restated from or exposed, not both.
5. The leak rule (Modules, rule 4) holds for restatements.
6. A folder without an `api.ctx` is no boundary: modules nested in a folder that is only a folder are visible to everyone through their own apis.

There is no list of names (`export gff::{ read, Gff }`), which would show names without their signatures and couldn't narrow a type; no renaming, which gives one function two names to learn and search for; no way for a nested module to make itself visible past its parent, whose surface is its own to decide; and no `expose` with exceptions, since restating exposes part of a module. The word is `expose`, not `export`: `export` brings TypeScript's forms with it (`export fn`, `export { a as b }`), each an error here, and in a language this close to C it means making a symbol visible to the linker, which `#c::export` does.

<!-- context:
// file: formats/build.ctx
fn build { mut b: Build } {
    let exe = build::exe{ &b, name = "viewer", root = "." }
    build::add_sources{ &b, exe, dir = "gff" }
    build::add_sources{ &b, exe, dir = "tpc" }
}
// file: formats/shared.ctx
namespace shared { fn twice { n: usize } -> usize { return n * 2 } }
// file: formats/gff/api.ctx
namespace gff {
    struct Gff { size: usize }
    error bad_magic
    fn read { bytes: []u8 } -> error(bad_magic)!Gff
}
// file: formats/gff/read.ctx
namespace gff {
    fn read { bytes: []u8 } -> error(bad_magic)!Gff {
        if bytes.len == 0 { return bad_magic }
        return Gff{ size = shared::twice{ n = bytes.len } }
    }
}
// file: formats/tpc/api.ctx
namespace tpc { fn decode { n: u32 } -> u32 }
// file: formats/tpc/decode.ctx
namespace tpc { fn decode { n: u32 } -> u32 { return n + 1 } }
// file: formats/main.ctx
fn main {} -> i32 {
    let g = gff::read{ bytes = "abc" } iferr { return 1 }
    return @as(i32, tpc::decode{ n = 1 })
}
// file: formats/api.ctx
...
-->
```ctx
// lib/formats/api.ctx
namespace gff {
    type Gff                                     // narrowed: opaque past this boundary
    error bad_magic
    fn read { bytes: []u8 } -> error(bad_magic)!Gff
}
expose "tpc"
```

## 11. Statements and control flow

```text
let x = e      let mut x = e      let x: T = e      let x: T      let mut x: T
let variant{ f, g = y } = e else { }      let ok{ value } = e else err{ error } { }
x = e
_ = e
if e { } else if e { } else { }
while e { }
for i in lo..hi { }      for x in e { }      for &x in e { }      for x at i in e { }
label: while e { }       label: for x in e { }
break      break label
continue   continue label
match e { ... }
return e
return
defer f{ ... }      defer x = e      defer if e { }      defer { }
f{ ... }
{ ... }
```

1. Conditions and match scrutinees need no parentheses: the block's `{` ends them. Parentheses are allowed, as around any expression.
2. `{` after `else` or `=>` begins a block. In a condition or scrutinee, outside any brackets, a `{` after an expression begins a call or literal only if the expression goes on after its matching `}`: with a token on the same line that isn't `else`, `;`, `,`, `}`, `)` or `]`, or on the next line as rule 3 has it. Otherwise it begins the block: in `if ok{ r } { }` the first `{` is a call and the second the block, and in `if done { }` the `{` is the block. Everywhere else, `{` after an expression begins a call or literal. In a let-else, `{` after the `else`'s variant holds its pattern if another `{` follows its `}`, and is the block otherwise.
3. Statements are separated by newlines or `;`. An expression goes on to the next line where that line starts with a token that continues an expression and begins none: a binary operator other than `-` and `&`, `and`, `or`, `is`, a handler (`ifnull`, `iferr`, `ifoverflow`), or the `.` of a field or a `.*`. That is so in a condition, a `let`'s or an assignment's value, an argument and a `return`'s value alike, and after a call's `}` as after anything else:

   <!-- context:
   struct World { open: bool }
   namespace door { fn open { w: World, d: u32 } -> bool { return w.open and d > 0 } }
   namespace inventory { fn has { w: World, key: u32 } -> bool { return key > 1 } }
   fn price { item: u32 } -> i64 { return 3 }
   fn decide { w: World, d: u32, key: ?u32, item: u32, count: i64, a: []u8, b: []u8 } -> bool {
       ...
   }
   fn main {} {}
   -->
   ```ctx
   if door::open{ w, d }
      or key != null and inventory::has{ w, key } { return true }
   let total = price{ item }
       * count
   return a.len == b.len
       and slice::eq_bytes{ a, b }
   ```

   `-` and `&` begin an expression too (`-1`, `&x`). A line that starts with one goes on with the expression before it, as the binary operator (`a`, then `- b`, is `a - b`), but for one place: after a `}` in a condition, which may have ended the condition's block, it begins a statement, as it did before lines continued: `if c { f{} }` with `-1` on the next line is an `if` and its block's value. There the `{` begins the block (rule 2), and if the condition was meant to go on, the error is at that line's `-`: ``a condition can't go on with a line that starts with `-`, which may begin a statement: end the line before with the `-`, or put the condition in parentheses``. It is the error where the line isn't a statement or the braces aren't a block of statements, and also where both readings parse, the braces as a call's items and the line ending in braces that could be the block (`if f{ n }`, then `- 1 > 0 { i = 1 }`), which only the types would tell apart: a value of its own there goes in parentheses, `(-g{ n })`. Braces that hold a match's arms are never a call's, so an operator on the line after a `match` expression applies to its value. A postfix `{`, `[` or `(` must be on the same line as the expression before it, and a `return`'s value begins on its line.
4. Every block is a scope. A `let` is visible from its declaration to the end of its block. A block may stand as a statement of its own, `{ ... }`: a scope whose locals end, and whose deferred bodies run (§11, Defer), at its `}`. It gives no value, so a branch can't end in one for its value. Its `{` begins the statement: a `{` on an expression's line is that expression's call or literal (rule 3).
5. In `x = e`, `x` must be a mutable place.
6. An expression statement must be a call or a builtin call that returns nothing, `try` of such a call, or `iferr` on a bare `!` (§8, Errors). A call that returns a value is an error as a statement, a `!T` or `!` included: use the value, or discard it explicitly with `_ = e`. `_ = e` evaluates any expression `e` that has a value, and drops it; `_` is not a name and can't be declared. In `_ = e ifnull x` and `_ = e iferr x`, `x` may also give no value, since the value is dropped either way: a block that ends without one, a trailing `if` or `match` among them, or a call that returns nothing. It runs for its effects (`_ = f{} iferr { log{} }`), and the `ifnull` or `iferr` then has no value, as one on a bare `!` has none. An `x` that is itself an `ifnull` or `iferr` may end so too. So `_ = f{} iferr { ... }` is right whatever `f` returns. The exception is the last statement of a branch of an `if` or `match` expression, which gives the branch its value (below).
7. `return` without a value is only allowed in a function with no `-> R`. In a function with `-> R`, every path must end in `return e` or `@panic()`. In a function with no `-> R`, or whose result is a bare `!` (§8, Errors, rule 4), `return e` may also take an `e` without a value: a call that returns nothing, `try` of one that returns a bare `!`, or an `iferr` on one. It is `e`, then `return`: `return try close{ &fs, file }`.
8. `break` leaves the innermost enclosing loop, a `while` or a `for`. `continue` skips the rest of its body and goes to its next condition check, or to a `for`'s next element or number. Both are errors outside a loop, and both end a path.
9. `while true` without a `break` that leaves it ends a path, like `return`.
10. Labels: `name:` before a `while` or a `for`, on the same line or the line above, labels it. Only a loop can be labeled. `break name` and `continue name` act on the enclosing loop labeled `name` instead of the innermost one, leaving any loops in between. It is an error if no enclosing loop has that label, or if a loop is labeled with a name an enclosing loop already uses. A jump in a `defer` body sees only the loops inside that body (§11, Defer). Deferred bodies run for every block the jump leaves, innermost first.

<!-- context:
fn find { grid: [3][3]i32, want: i32 } -> usize {
    let n: usize = 3
    let mut r: usize = 0
    ...
    return r
}
fn main {} {}
-->
```ctx
rows:
while r < n {
    let mut c = 0
    while c < n {
        if grid[r][c] == want { break rows }
        c = c + 1
    }
    r = r + 1
}
```

### For

<!-- context:
fn find { xs: []mut i32, grid: [3][3]i32, want: i32 } -> usize {
    let n: usize = 3
    let mut total: i32 = 0
    ...
    return 0
}
fn main {} {}
-->
```ctx
for i in 0..n { total = total + xs[i] }             // i has n's type: 0, 1, ... n - 1
for x in xs { total = total + x }                   // each element, copied
for &x in xs { x = x * 2 }                          // each element's place: xs is a []mut T or a mutable array
for x at i in xs { if x == want { return i } }      // the element and its index, a usize
rows:
for r in 0..n {
    for c in 0..n { if grid[r][c] == want { break rows } }
}
```

1. `for i in lo..hi { B }` runs `B` with `i` set to `lo`, `lo + 1` and so on up to `hi - 1`: `hi` is left out, and where `lo >= hi` the body doesn't run at all, so a range never counts down. `lo` and `hi` are evaluated once, `lo` first, before the first turn: what the body does to the places they read doesn't change the range. They are integers of one type after widening, as the operands of `<` are (Expressions, rule 1), and `i` has that type: in `for i in 0..n` it is `n`'s, and between two literals `i32`, unless a use says otherwise (Literals, rule 1). Counting never overflows. `lo..=hi` is an error: write `lo..hi + 1`.
2. `for x in e { B }` runs `B` once for each element of `e`, in order, with `x` a copy of the element. `e` is a slice; or an array place, a pointer to an array or a const array, gone over as its view `e[..]` (§12, Slices, rule 4); or an array literal, which is a view where a slice is expected (Literals, rule 4). An array that isn't a place, as a call's result, is an error: keep it in a `let` first. Anything else is an error that says what to go over: for a number `n`, `0..n`; for a list, `list::items{ list = xs }`.
3. `for &x in e { B }` binds `x` as the element's place instead, as `&f` binds a field in a pattern (§8, Match, rule 5). Nothing is copied. `x` is mutable where `e` is a `[]mut T` or a mutable array place, and read-only otherwise. `&x` is the element's address, derived from what `e` is derived from (§14, Escape check).
4. `for x at i in e`, and `for &x at i in e`, also set `i`, a `usize`, to the element's index. Two names with a comma, `for a, b in e`, are an error that says to write `at`: which of the two is the index would be easy to get wrong. A range has no `&` and no `at`.
5. The names are the body's own, set anew each turn: `i`, an `x` without `&` and the index are read-only locals, so assigning one is an error (change a `let mut` copy), and a bind made in the body holds that turn's value. `_` for a name declares nothing: `for _ in 0..n`.
6. What is gone over is evaluated once, before the first turn, and the loop holds that slice as a `let` holds one: its length is fixed then, and each turn reads its element as it is at that turn, so a later turn sees what an earlier one changed. Nothing tracks what a held slice points to (§12, Pointers, rule 7). So a body that frees or moves the memory, as growing a list while going over its items may, leaves the loop with a slice of memory that is gone, as it would leave any slice held across that call (§13, Unchecked operations, rule 3): go over the indexes instead, `for i in 0..xs.len`, whose `xs.len` is read once, and index the list in the body.
7. `break`, `continue` and labels act on a `for` as on a `while` (rules 8 and 10). A `for` never ends a path (rule 9): it may run no turn.
8. A `for` can't go over tasks' handles (§15, Tasks, rule 4), which are never copied: count the indexes.

### Let-else

<!-- context:
error odd
union Ref { decl{ i: u32 }, other }
const NONE: u32 = 0
fn half { n: u32 } -> !u32 {
    if n % 2 == 1 { return odd }
    return n / 2
}
fn peek { p: []u8 } -> ?u8 {
    if p.len == 0 { return null }
    return p[0]
}
fn first { n: u32, p: []u8, cached: ?u32, found: ?Ref } -> !?u32 {
    ...
    return h + @as(u32, c) + i
}
fn main {} {}
-->
```ctx
let ok{ value = h } = half{ n } else err{ error } { return error }
let some{ value = c } = peek{ p } else { return null }
let null = cached else { @panic() }
let decl{ i } = found else { return NONE }        // found: ?Ref; null takes the else too
```

1. `let P = e else { B }` matches `e` against the pattern `P`, which is a variant with optional bindings as in a match arm (§8, Match). `P` may not be `mut`, and bindings may not use `&`.
2. `e` must have a union or `?T` type. A pointer is an error: use `match`. On a `?U` for a union `U`, `P` may name a variant of `U`, as with `is` (§8, Is): `B` then runs for null too.
3. If `e` holds `P`'s variant, its bindings are read-only locals from after the statement to the end of the enclosing block, as if declared by `let`.
4. Otherwise `B` runs. `B` must leave: it ends a path (§11.7, 8, 9). `P`'s bindings aren't visible in it.
5. `else V{ ... } { B }` binds `V`'s fields in `B`. `V` must be the union's only variant other than `P`'s, and `P` can't be a variant of a `?U`'s `U`.

### If let

<!-- context:
struct Tlk { n: i32 }
struct W { tlk: ?Tlk }
fn show { n: i32 } {}
fn bump { mut t: Tlk } { t.n = t.n + 1 }
fn talk { mut w: W, m: map::Map(u32, i32, arena::Arena), key: u32 } -> i32 {
    ...
    return n
}
fn main {} {}
-->
```ctx
if let t = w.tlk { show{ n = t.n } } else { show{ n = 0 } }
let n = if let v = map::get{ m, key } { v } else { 0 }
if let &t = &w.tlk { bump{ &t } }               // t is the place inside w.tlk
```

1. `if let x = e { A } else { B }` takes an optional apart: if `e` holds a value, `A` runs with `x` a read-only local holding it; if `e` is null, `B` runs. It is `match e { some{ value = x } => { A } null => { B } }` (§8, Match), and is checked and runs as that match does.
2. `e` must have a `?T` type, or be a pointer to one. Unlike narrowing (§8, Optional, rule 3), `e` may be any expression, a mutable place or a call included: it is evaluated once, and `x` holds the value it had.
3. `x` is in scope in `A` only: not in `B`, and not after the statement, even when `B` leaves.
4. `if let &x = e`, for `e` a pointer to a `?T` (`&w.tlk`), binds `x` as the place inside the optional, as `some{ &value = x }` does (§8, Match, rule 5). It is mutable only through a `*mut`. As in a match on `&p`, nothing in `A` may reach `p` except through `x` (§8, Match, rule 7). Without a pointer, `&x` is an error.
5. As a statement, `else { B }` may be left out, and `B` is then empty. `else if` and `else if let` chain, as after an `if`. As an expression (§11, If and match expressions), `else` is required, and the value is the match's.
6. `if let` tests one optional, and doesn't combine with `and`, `or` or `not`: for that, use `is` (§8, Is), as in `if a > 0 and x is some{ value = v }`.

### Defer

<!-- context:
fn fill { mut heap: arena::Arena } -> ! {
    ...
    try list::push{ list = &xs, item = 1 }
}
fn main {} {}
-->
```ctx
let mut xs = list::new(i32){ realloc = arena::alloc, &heap }
defer list::free{ list = &xs }
```

1. `defer` takes a statement that can run later by itself: a call, an assignment, a discard (`_ = e`), an `if` or `if let`, a `match`, a `while` or a `for`, or a block. `defer s` is `defer { s }`, so `defer if c { f{} }` tests `c` when it runs. A `let` isn't one, since nothing could use its local: put it in a block with what does. Neither is a `return`, `break` or `continue` (rule 7), nor another `defer`. Its body runs when the enclosing block exits: at its end, or through `return`, `break`, `continue`, or a branch of an `if` or `match` expression leaving (§11, If and match expressions).
2. A block's deferred bodies run in reverse order of their `defer` statements. Only `defer` statements that were reached run.
3. The body is evaluated when it runs, not at the `defer`: `defer say{ n = i }` sees the value `i` has at exit. A `return e` evaluates `e` before deferred bodies run.
4. A `defer` inside a loop body runs at the end of each iteration that reached it.
5. Deferred bodies don't run when the program stops through `@panic()`, or when a test ends at a `@require` that doesn't hold (§13, Checks, rule 7).
6. The body is checked where it appears. It can read only variables that are assigned there (§11, Initialization), and it can't assign a `let x: T` declared outside it.
7. The body can't leave: `return` is an error in it, and `break` and `continue` in it must be inside a loop that is also in it.

### If and match expressions

<!-- context:
error bad
fn parse { s: []u8 } -> !i32 {
    if s.len == 0 { return bad }
    return 1
}
fn signed { n: i32, s: []u8 } -> !i32 {
    ...
    return v * sign
}
fn main {} {}
-->
```ctx
let sign = if n < 0 { -1 } else if n == 0 { 0 } else { 1 }
let v = match parse{ s } {
    ok{ value }  => { value }
    err{ error } => { return error }
}
```

1. `if` and `match` are statements at the start of a statement, and expressions everywhere else.
2. An `if` expression must have an `else`.
3. Each branch is a block whose last statement is an expression: the branch's value. `{ let y = f{}; y + 1 }` has the value `y + 1`. A match arm without braces is the block of its one statement (§8, Match, rule 11): `a => "A"` has the value `"A"`.
4. Instead of ending in a value, a branch may leave: it ends a path (§11.7, 8, 9) through `return`, `break`, `continue` or `@panic()`. At least one branch must produce a value.
5. A branch whose last statement is an `if` or `if let` with an `else`, or a `match`, takes that statement's value, unless every one of its branches leaves.
6. Type: if the expression has an expected type (§11, Widening, rule 1) that every branch value converts to, that type. Otherwise the first branch type that every other branch value converts to, where `null` among the branches makes it `?T`. It is an error if there is none.
7. Narrowing (§8, Optional) applies in the branches as in an `if` statement.
8. A branch value must not hold the address of, or a bound function holding, a local declared in that branch (§6, §14).
9. An `if` or `match` expression takes no postfix operators. To apply one, put the expression in parentheses.

### Expressions

Precedence, tightest first:

| Level | Operators | Notes |
|---|---|---|
| postfix | `.f` `.*` `[i]` `[lo..hi]` `{ ... }` `::x` `(G)` | left to right |
| prefix | `&` `-` `~` `not` `try` | `try`: §8, Errors; `not e is P` is `not (e is P)` |
| multiplicative | `*` `/` `%` `*%` | left to right |
| additive | `+` `-` `+%` `-%` | left to right |
| shift | `<<` `>>` `<<%` | left to right |
| bitwise and | `&` | left to right |
| bitwise xor | `^` | left to right |
| bitwise or | `\|` | left to right |
| handler | `ifnull` `iferr` `ifoverflow` | rule 7; the right side may be a block (§8, Optional, Errors; Overflow, below) |
| comparison | `==` `!=` `<` `<=` `>` `>=` `is` | don't chain: `a < b < c` is an error; `is`: §8, Is |
| and | `and` | short-circuit |
| or | `or` | short-circuit |

1. Arithmetic and comparison apply to two operands of the same numeric type, after widening (below). If the operand types differ, the one that widens to the other is converted. If neither widens to the other, it is an error, unless one is a const's name whose value fits the other's type (Widening, rule 7). Use `@as` or `@trunc` (§13).
   - `<`, `<=`, `>` and `>=` order numbers and nothing else: integers, floats, and two values of one distinct type whose base is a number (§12). A `bool`, an enum (§12, Enums) and a pointer have no order, and none is derived for a struct, a union, an array or a slice as `==` is (rule 5): the order of its fields would set it without a word. With a NaN operand all four are false.
   - In a generic function (§9) two values of a parameter's type may be ordered: `a < b` for two `T`s. Every use of the function must then give that parameter a type with an order, through the generic functions between too, and one that doesn't is an error where the function is named, which says `<` for all four: ``` `largest` uses `<` on its `T`, and Point has no `<`: it is a struct, and only numbers have an order: order two of them by a number of their own, or call a function that takes the order as a `less` function ```. Both operands have the parameter's type itself: a literal, a value of another type, or of a type with the parameter in it (`[]T`, `?T`) is an error in the function. For a type without an order a function takes the order as a function instead, as std's `cmp::min_by` takes `less` (§17).
2. Integer `+ - *` panic on overflow, unless an `ifoverflow` covers them (Overflow, below). `/` and `%` panic on a zero divisor. `+%`, `-%` and `*%` are the same arithmetic modulo 2^N, for an N-bit type: they wrap instead of overflowing, as a hash, a random number generator or a format's C does (`state *% 214013 +% 2531011`), and cost no check where nothing can overflow. They apply to two operands of the same integer type, after widening as in rule 1.
3. `&`, `|` and `^` apply to two operands of the same integer type, after widening as in rule 1, and `~` to one integer, whose bits it flips: `flags & ~SELECTED` clears a flag. They act on the two's complement bits and never panic.
4. `a << n` and `a >> n` shift integer `a` by `n` bits. The result has `a`'s type. `n` may have any integer type and doesn't widen to or from `a`'s. A count below 0, or at or above `a`'s width in bits, panics. `a << n` is `a * 2^n` and panics where that overflows, as `*` does (rule 2). `a <<% n` drops the bits shifted out instead, as `*%` wraps: it is `a *% 2^n`, with `<<`'s operands, result type and place in the table above, and never overflows (`h <<% 5`, `1 <<% 31` for an `i32`'s sign bit). Its count is checked as `<<`'s is: one below 0, or at or above `a`'s width, still panics. `>>` is arithmetic for signed types (it copies the sign bit) and logical for unsigned ones.
5. `==` and `!=` compare two values of one type. Each operand is evaluated once, left to right.
   - Numbers, `bool`, and two values of one enum (§12, Enums) compare by value, and pointers by address.
   - A **value type** compares by its parts, each with its own `==`: a struct field by field; a union by its variant, and then that variant's fields; an array element by element; a slice, `[]T` or `[]mut T`, by its length and then its elements, so two `[]u8` are equal when they hold the same bytes, wherever those are; a `strlit` as its bytes; a distinct type as its base (§12). `p == q` on two `Point`s, `a.name == b.name` on two `utf8::String`s and `key == "fn"` on a `[]u8` are these. Nothing is written for it, and a field added later is compared too. The comparison stops at the first part that differs and never reads padding. A slice is compared by contents because it is how ctxlang holds a string and a list: by address, two equal names would differ, without a word.
   - Each part of a value type is a number, a `bool`, an enum or a value type. A type with another part has no `==`, and the error names the part and says why: ``Node has no `==`: its `next` is a *Node, a pointer, which a value's `==` neither follows nor compares: compare the fields by hand, the pointer by its address or by what it points to``. A pointer inside a value is refused rather than compared by address, which is rarely what makes two values equal (a `c::String` is one pointer), or followed, which may never end. A function, a capability, an `extern union` (which field holds its value isn't known), an error and a `!T` have none either, at the top or inside.
   - Floats compare as IEEE 754 has it, alone or inside a value: `-0.0 == 0.0`, and a NaN equals nothing, so a value that holds one isn't equal to itself. That is why `@hash` refuses them (§13, Hashing).
   - A `?T`, for a `T` with `==`, compares with `null`, with a `T` and with another `?T`: a null equals only a null, and two values compare as their `T`s do, after widening as in rule 1. So `x == 3` is false and `x != 3` true where `x` is null. `x == v` narrows `x` (§8, Optional, rule 4). A `??T` compares only with `null`.
   - In a generic function (§9) a value whose type has a parameter in it may be compared: `v == x` for two `T`s, or two `[]T`. Every use of the function must then give that parameter a type with `==`, through the generic functions between too, and one that doesn't is an error where the function is named: ``` `index_of` uses `==` on its `T`, and Node has no `==`: its `next` is ... ```.
   - A derived `==` is code that runs, not folded: a const that uses one is run (§14, rule 1).
6. `and`, `or` and `not` take and give `bool`. Conditions must be `bool`.
7. The **handlers** are `ifnull`, `iferr` and `ifoverflow`, and one rule places all three: a handler has the operators of the levels above it on each side, and never sits beside one of the levels below it.
   - Its left side is the operand before it, with the arithmetic and bitwise operators there: all `ifoverflow` covers in `a * b + c ifoverflow x`, and the call an `ifnull` or an `iferr` handles.
   - Its right side is a block, or an expression. An expression goes as far as the left side would, and takes every handler after it: `a ifnull n + 1` is `a ifnull (n + 1)`, and `a ifnull b ifnull 0` is `a ifnull (b ifnull 0)`, which tries `a`, then `b`. A block ends at its `}`, so a handler after a block takes the whole expression before it, on the same line or the next: `f{} iferr { return } ifnull { return }` is `(f{} iferr { return }) ifnull { return }`, a `!?T`'s value, or leaving.
   - Handlers of both kinds go in the order of the type, outside in: the error of a `!?T` first, the null of a `?!T` first. The other order is an error that says so (``handle its error first, as `f{} iferr { ... } ifnull { ... }` ``), and so is a second handler of one kind after a block, which has nothing left to handle.
   - Beside a comparison, `is`, `and` or `or`, a handler is written in parentheses, its own or ones that take the other operator in. `x == f{} ifnull y` is an error that shows both: ``write `x == (f{} ifnull y)` or `(x == f{}) ifnull y` ``. So are `f{} ifnull a == b`, `c and f{} ifnull d` and `a + b ifoverflow 0 < n`. Other languages put their `??` below comparison, where a handler here would be above it, so neither reading is left to a guess. A handler on the left whose right side is a block reads one way and needs none: `f{} ifnull { return } == y`.
   - An `ifnull` or an `iferr` after an operator's expression would take all of it, and an operator's result is never an optional or a `!T`: `a + f{} ifnull 0` is an error that says to write `a + (f{} ifnull 0)`, and `not f{} ifnull false` to write `not (f{} ifnull false)`. A left side in parentheses, `(a + b) ifnull 0`, is taken as written.

### Overflow

`e ifoverflow x` is `e`'s value, unless an operation `e` covers overflows. Then `e` stops there, and the value is `x`'s. `x` is an expression, or a block that gives a value or leaves, as after `ifnull` (§8, Optional, rule 7).

<!-- context:
error too_big{ count: u32 }
fn sizes { count: u32, len: usize, a: i32, b: i32, c: i32 } -> !u32 {
    ...
    return size + n + @as(u32, total)
}
fn main {} {}
-->
```ctx
let size = count * 16 ifoverflow { return too_big{ count } }
let n = @as(u32, len) ifoverflow 0
let total = a * b + c ifoverflow 0                  // covers the * and the +
```

1. `e` covers its own operation if it is an integer `+`, `-` or `*`, a signed integer `/`, a unary `-` of an integer, or an `@as` or `@round` to an integer type (§13); and if it is one of these or another integer operator (an unsigned `/`, `%`, `&`, `|`, `^`, `~`, `<<`, `>>`, `<<%`, `+%`, `-%`, `*%`), what its operands cover, in turn. Nothing else is covered: not a call's arguments, an index, a comparison's operands, nor what a nested `ifoverflow` covers, which is its own. Parentheses change nothing.
2. An operation overflows when its result isn't a value of its type: `+`, `-`, `*` and unary `-` past the type's range, `/` of the type's minimum by -1, and an `@as` or `@round` to an integer type whose value isn't representable in it (a float's after rounding toward zero, or for `@round` to nearest; NaN and the infinities never are). `@saturate` and `@round_saturate` never overflow: they clamp (§13). An `@as` to a float type never overflows: it rounds, past `f32`'s range to an infinity (§13). A covered operation that overflows doesn't panic. A zero divisor, a shift count out of range, and an operation nothing covers still panic. `%` never overflows: `MIN % -1` is 0.
3. `e` is evaluated as it is without `ifoverflow`, left to right, up to the operation that overflows. What it evaluated stays done, and the rest of it isn't evaluated: in `f{} * g{} + h{} ifoverflow 0`, if the `*` overflows, `f` and `g` have run and `h` doesn't.
4. It is an error if `e` covers nothing, as in `x ifoverflow 0`, or `(a * b < n) ifoverflow false`, where a comparison's operands aren't covered (rule 1): write `a * b < n` with the handler on the arithmetic, `(a * b ifoverflow x) < n` (Expressions, rule 7).
5. The value's type is as for an `if` expression whose branches are `e` and `x` (If and match expressions): `e`'s, unless `x` gives a type `e`'s widens to. `e`'s arithmetic is in its own type either way.
6. `x` may run after any of `e`'s covered operations, so a local `e` assigns may be assigned there (Initialization).

### Widening

A value of numeric type `A` converts implicitly to numeric type `B` when every value of `A` is a value of `B`:

| From | Widens to |
|---|---|
| `iN` | `iM` for M > N |
| `uN` | `uM` and `iM` for M > N |
| `u8`, `u16`, `u32` | `usize` |
| `usize` | `u64` |
| `f32` | `f64` |

1. Widening applies wherever an expression of type `B` is expected: a read-only call argument, a struct or union field, an assignment, a `let` with a type, a `return`, and the `T` of an implicit `T` to `?T` conversion. It also applies between the operands of a binary operator (rules 1 and 3 above), but not to a shift count.
2. A `*mut T` converts implicitly to `*T`, a `[]mut T` to `[]T`, and a `?*mut T` or `?[]mut T` to `?*T` or `?[]T`, wherever rule 1 applies and between the operands of `==` and `!=`.
3. Wherever rule 1 applies, a `*[N]T` converts implicitly to a `[]T`, and a `*mut [N]T` to a `[]mut T` or `[]T`: the slice of the whole array. An array value doesn't, but an array literal there is a view of its array (Literals, rule 4).
4. Wherever rule 1 applies, a capability converts implicitly to one it includes (§15, rule 10).
5. Nothing else converts implicitly, but a const's name (rule 7). In particular a distinct type (§12) converts to and from no other type, not even its base, and doesn't widen; integers don't widen to floats, `usize` doesn't widen to a signed type, `*T` doesn't convert to `*mut T` nor `[]T` to `[]mut T`, and `?A`, `*A` and `[N]A` don't convert to `?B`, `*B` and `[N]B`. A `mut` field's argument is a `*mut` pointer, so its type must match exactly, except that it may point to a capability that includes the field's (§15, rule 10).
6. `usize` is at least 32 and at most 64 bits wide on every target, which is what makes the `usize` rows lossless.
7. **A const's name converts where its value fits.** The name of a const, with its path (`gl::LINEAR`), whose type is an integer type and whose value is folded (§14, rule 1), converts implicitly to another integer type where its value is a value of that type, as an integer literal of that value would: wherever rule 1 applies, as a `match` pattern (§8, Match on integers), and as one operand of a binary operator whose other operand has that type. So `tex_parameteri{ param = gl::LINEAR }` takes the `u32` const for an `i32` field, and `x == gl::LINEAR` compares it with an `i32`. Where the value doesn't fit, it is an error that gives the value: a `u32` const of 300 is no `u8`. The conversion is tried only where the types neither agree nor widen, so it changes no program that compiled without it. Only the name converts: not an expression of consts (`gl::A | gl::B` keeps their type; name it in a const), not a const whose value is computed by running code (§14), which isn't known while the bodies are checked, and not a local, a field or a call's result, whose values aren't known at all. Nor does a const of a distinct type or an enum convert, or any const convert to one (rule 5), or an integer const to a float type. Everywhere else the const has its own type: `let n = gl::LINEAR` is a `u32`.

### Literals

1. An integer literal is decimal (`42`), hexadecimal after `0x` (`0xFF`, `0x1f`), or binary after `0b` (`0b1010`); there is no octal. `_` among its digits is ignored: `1_000_000`, `0xFFFF_0000`. It has an integer type that is inferred from every use within the enclosing function body, including uses of locals it initializes. If no use fixes it, it is `i32`.
2. A float literal (`1.5`, `2e3`) is inferred the same way among float types, and defaults to `f64`. It rounds to the nearest value of its type, a tiny one to zero, but a literal that would round to an infinity is an error, as `1e300` is for an `f32` and `1e999` for any type: the infinities are std's `math::INF` and `math::INF_F32` (§17), and the error says so.
3. `true` and `false` are the `bool` values. `null` is described in §8.
4. `[a, b, c]` is a `[3]T` array. Every element has type `T`. Where a `[]T` is expected (Widening, rule 1, also inside `?` or as a `!T`'s value, and as the value of an `if` or `match` branch that has one), it is instead a **view** of that array, a `[]T`, with each element checked against `T`: so `[[1, 2], [3]]` where a `[][]u32` is expected is a view of two views, `["a", "bb"]` where a `[]utf8::String` is converts each literal, and `[]` is the empty view. The view is read-only: where a `[]mut T` is expected it is an error.
   - If every element is known while compiling (what folding computes, §14, a string literal converted by a `#convert` fn, or a static view), the array is computed while compiling, as a folded const is (so what would panic is an error at the operation), and is in static read-only memory, as a const array's view's is (§12, Slices). The view is derived from nothing (§14, Escape check): it may be returned or stored anywhere, and be a const's value where the const is folded (§14), as `const WORDS: [][]u8 = ["fn", "let"]` is (with a converted literal among the elements the const is evaluated instead, and can't hold the view). In a generic function (§9) the array is always a local, as below, since it would be computed once for every instance.
   - Otherwise the array is a hidden read-only local of the innermost enclosing block, set each time the literal is evaluated (in a loop, on each iteration), and the view is derived from it (§14, Escape check): returning it, or storing it where it outlives the block, is an error, as it is for `&x[..]` of a local `x`. A branch's value leaves the branch, so a view in it (also nested in it, as `[[a], [b]]` or a struct literal's field) is a local of the block around the `if` or `match`, or around the outermost one whose branch value holds it: `let xs: []u32 = if c { [a, 2] } else { [3] }` is fine. One in a branch's statements is the branch's.
5. `[x; N]` is a `[N]T` array with every element a copy of `x`. `N` is a compile-time integer constant (§14). Where a `[]T` is expected it is a view of that array, as in rule 4.
6. A string literal `"..."` holds `N` bytes. Its type depends on the type expected where it appears (also inside `?`):
   - `strlit` (§12): the literal itself. Its `bytes` are static and read-only, and live for the whole program.
   - a type `T` that a `#convert` fn gives (§18, Literal conversions): that fn's result for the literal, computed while compiling. So std makes a literal a `utf8::String` (§17), whose bytes must be valid UTF-8, or a `c::String` (§18), which can't hold a NUL itself (`\0`), since C would end the string there.
   - `[N]u8`, for the literal's `N`: an array value holding a copy of the bytes. Like any array it is a value, not a place: bind it to a `let mut` to write into it, as `let mut s: [3]u8 = "abc"`.
   - anything else, or nothing: a `[]u8`, a **view** of those bytes. So `let pre = "gui_"` is a `[]u8`, and so is each element of `["a", "bb"]`. `[]mut u8` is an error.

   A literal's static bytes are followed by a 0 byte that isn't one of them, the **hidden zero**: `"abc"` as a `[]u8` has `len` 3, and its `(ptr + 3).*` is 0, and `""`'s `ptr.*` is 0. So a pointer to a literal's bytes is a C string as it is, and nobody writes `"abc\0"` for C.

   In an `if` or `match` expression without an expected type, a branch that is a literal takes the type of another branch that is a `strlit`, a `[]u8` or a type a `#convert` fn gives, or of another literal branch that became one because one was expected: `if c { name } else { "none" }` is a `utf8::String` when `name` is one. Otherwise, as in `let msg = match p { a => { "one" } b => { "three" } }`, each literal is a `[]u8`.
7. A character literal `'a'` is an integer literal whose value is the character's byte.
8. String and character literals hold ASCII characters only. Escapes, except in a multi-line literal: `\n`, `\t`, `\r`, `\0`, `\\`, `\"`, `\'`, and `\xNN` for any byte.
9. A **multi-line literal** is a string literal written as lines that each start with `\\`, with only spaces and tabs before it on its line. Each line's text is what follows its `\\`, as it is: there are no escapes, and a `\r` that ends the line isn't part of it. The literal's bytes are those texts joined with `\n`, with none after the last; an empty `\\` line at the end adds one. It ends at the first line that doesn't start with `\\`, so a comment can't be among its lines. Otherwise it is a string literal like any other (rule 6), for GLSL or any other text:
   <!-- context:
   fn main {} {}
   -->
   ```ctx
   const MESH_VS: c::String =
       \\#version 410 core
       \\layout(location = 0) in vec3 pos;
       \\void main() { gl_Position = vec4(pos, 1.0); }
   ```

### Places

```text
place := root step*
root  := local | context field | match binding | expr.*
step  := .field | [index]
```

1. For a pointer `q`, `q.f` is a place rooted at a deref (§12), and so is `q[i]` for a pointer to an array. So is `s[i]` for a slice `s`.
2. A place **goes through a deref** if its root is `expr.*`.
3. A place is **mutable** if its root is a `let mut` local, a `mut` context field, or a `&f` match binding through a `*mut` (§8), or if it goes through a deref of a `*mut` pointer or a `[]mut` slice: `q.*`, `q.f` or `(q + i).*` for `q: *mut T`, and `s[i]` for `s: []mut T`.
4. Every other place is read-only.

### Initialization

1. `let x: T` without an initializer: `x` must be assigned exactly once on every path before it is read. An assignment inside a loop is allowed only if no path leads from it back to the loop's next iteration, for example because a `break` follows it.
2. `let mut x: T` without an initializer: if `T` has a zero value, `x` starts as that value. Otherwise `x` must be assigned on every path before it is read.
3. Zero values: a type has one exactly when its bytes all zero are a value of it, which is what memory a program hasn't written holds (a `let` without an initializer, a static, an allocation).

| Type | Zero value |
|---|---|
| integers, floats | `0` |
| `bool` | `false` |
| `?T` | `null` |
| `[N]T` | every element zero, if `T` has a zero value |
| `[]T`, `[]mut T` | the empty slice |
| struct | every field zero, if every field type has a zero value; field defaults don't apply (§7, rule 5) |
| enum | its variant whose value is 0 (the first, unless values are given), if it has one |
| union | its first variant, with every payload field zero, if they all have zero values |
| `*T`, `*mut T`, `strlit`, `fn{C} -> R`, `&fn{C} -> R`, capability types | none: zero bytes are no value of these (a pointer is never null) |

4. Reading a variable before it is assigned is a compile error. There is no way to declare uninitialized memory.

## 12. Types

| Syntax | Meaning |
|---|---|
| `i8..i64`, `u8..u64`, `usize`, `f32`, `f64`, `bool` | primitives |
| `*T` | read-only pointer to a `T`. Never null. |
| `*mut T` | pointer to a `T` that can be written through. Never null. |
| `[N]T` | fixed array. `N` is a compile-time integer constant (§14), or `_` in a `let`'s or a const's type (Arrays, rule 3). |
| `[]T` | read-only slice: a pointer to `T`s and a length. |
| `[]mut T` | slice whose elements can be written. |
| `?T` | optional (§8). `?*T` is a nullable pointer. |
| `!T`, `!` | a value or an error (§8, Errors). |
| `error` | any error (§8, Errors). |
| `strlit` | a string literal (§11, Literals): `s.bytes` is its bytes, a `[]u8` followed by the hidden zero, and isn't a place. Only a literal makes one: it has no zero value, and nothing converts to it. A `#convert` fn takes one (§18). |
| `enum Name: T { ... }` | integer type with named values (below) |
| `fn{C} -> R` | unbound function type (§5) |
| `&fn{C} -> R` | bound function type (§5, §6) |
| `extern fn{C} -> R` | C function pointer (below, §18) |
| `extern union Name { f: T, ... }` | C's untagged union (below, §18) |
| `type Name(G) = T` | alias: another name for `T`, which mixes freely with it |
| `type Name(G) = distinct T` | a new type with `T`'s representation (below) |

### Pointers

1. `&p` is the address of place `p`. It is allowed on any place. Its type is `*mut T` if `p` is a mutable place (§11), and `*T` otherwise.
2. `q.*` is the place that pointer `q` points to.
3. If `q` is a `*S` for a struct `S`, `q.f` means `q.*.f`.
4. `q + n`, with `n: usize`, points `n` elements of `T` after `q`. It has `q`'s type.
5. A pointer can't be indexed: `q[i]` is an error, since `[i]` is bounds-checked and a pointer has no length to check against. The element `i` after `q` is written `(q + i).*`, which is not bounds-checked; the error spells it, with `@as(usize, i)` for an `i` of another integer type. `q[lo..hi]` is an error too: `@slice(q + lo, n)` makes the slice (§13).
6. Exception: if `q` is a `*[N]T`, `q[i]` means `q.*[i]` (bounds-checked) and `q.len` means `N`.
7. Pointers aren't tracked. Using a pointer to memory that no longer exists, or outside its allocation, is undefined behaviour. The operations that can make such a pointer are the unchecked operations (§13), which a build can deny outside the directories it names.
8. A place reached through a `*T` is read-only: assigning to it, or passing it as `&p` to a `mut` field, is an error. Through a `*mut T` it is mutable (§11).

### Arrays

1. `a[i]` on an array is bounds-checked: an index below 0, or at or past the length, panics, with a message that gives the index and the length (`index -1 out of bounds for length 3`). `i` is an integer of any type, signed or not, but not a distinct type or an enum, which `@as` converts: game data's `i32` indexes a table as it is, and the check that it is in range is the index's own. The check costs the same for every type: a signed index is compared as its bits, which below 0 are past any length. An integer literal as an index is a `usize`, so `a[-1]` is an error while compiling.
2. `a.len` is `N`, of type `usize`.
3. A `let`'s or a const's type may be `[_]T`: the array's length is its initializer's, which must be an array or string literal, as in `const NAMES: [_][]u8 = ["fn", "let", "match"]`, a `[3][]u8`. Only the outermost length may be `_`; `[_]T` anywhere else is an error.

### Enums

<!-- context:
fn main {} {}
-->
```ctx
enum Kind: u8 {
    ident,                  // 0
    number,                 // 1
    lbrace = 40,
    rbrace,                 // 41
}

fn code {} -> usize {
    let k = Kind::lbrace
    if k == Kind::rbrace { return 0 }
    return @as(usize, k)    // 40
}
```

1. An enum is an integer type with named values. `T`, its base type, is one of `i8`..`i64`, `u8`..`u64` and `usize`. An enum has `T`'s size, alignment and representation.
2. Variants have no payload. The first variant's value is 0, and each later one's is one more than the variant before it, unless `= e` gives it a value. `e` is a compile-time integer constant (§14). It is an error if a value doesn't fit in `T`, or if two variants have the same value.
3. An enum can't have generic parameters.
4. `Name::v` is variant `v`'s value, of type `Name`. An enum converts implicitly to and from no other type (§11, Widening), and its zero value is its variant whose value is 0, if it has one (§11, Initialization).
5. `==` and `!=` compare two values of the same enum. No other operator applies to enums.
6. `match` takes an enum scrutinee as it takes a union one (§8, Match): arms list variants, the arms must be exhaustive, and patterns have no bindings. So does `is` (§8, Is): `k is lbrace | rbrace`. The scrutinee can't be a pointer to an enum: match on `p.*`. `let` with a pattern (§11, Let-else) doesn't apply to enums.
7. `@as(U, x)` gives the value of enum `x` in integer type `U`, and panics if it doesn't fit. `@as(E, n)` gives the variant of enum `E` whose value is integer `n`, and panics if there is none (§13).
8. A const may hold enum values (§14).

An enum is for a closed set whose values matter: table indexes, file formats, a chosen size. A union whose variants have no payload is for a closed set whose values don't.

### Distinct types

<!-- context:
fn main {} {}
-->
```ctx
type Meters = distinct f64
type Seconds = distinct f64
type Id(T) = distinct u64              // Id(User) and Id(Order) are different types

fn speed { d: Meters, t: Seconds } -> f64 { return @as(f64, d) / @as(f64, t) }

fn run {} -> f64 {
    let d: Meters = 5.0
    let far = d + d * 2.0                  // a Meters
    _ = speed{ d = far, t = @as(Seconds, 2.0) }
    return speed{ d = 2.0, t = far }       // error: expected Seconds, got Meters
}
```

1. `type Name(G) = distinct T` declares a new type, `Name`, whose **base** is `T`, which may be any type. It has `T`'s size, alignment and representation, so C sees a `T` where an extern fn (§18) takes or returns one. Its generic parameters need not appear in `T`: `Id(User)` and `Id(Order)` are two types.
2. A distinct type converts implicitly to and from no other type, not even its base (§11, Widening). `@as(Name, x)` converts `x`, a `T`, to `Name`, and `@as(T, d)` converts `d`, a `Name`, to `T`: no other `@as` applies to it. Both cost nothing at run time.
3. An integer or float literal takes a distinct type whose base is a number as it would take the base (§11, Literals): `let d: Meters = 5.0`. A string literal doesn't: `@as(Name, "bob")` makes one of a `type Name = distinct []u8`.
4. If `T` is a number, the arithmetic (`+%`, `-%` and `*%` too), bitwise, shift (`<<%` too) and comparison operators and unary `-` and `~` apply to `Name`s as to `T`s, with `T`'s overflow and panics (which an `ifoverflow` covers as a `T`'s), and give a `Name` (a comparison a `bool`). Both operands are `Name`s, or one is a literal: a `T` or another distinct type is an error, which `@as` resolves. A shift count is an integer that isn't a distinct type, as for `T`. If `T` is an integer, `match` and `is` take a `Name` as they take a `T` (§8, Match on integers).
5. `==` and `!=` apply to a `Name` if they apply to a `T`. Nothing else applies to a distinct type: a distinct struct has no fields, and a distinct slice no `len` or index, until `@as` gives the `T`.
6. A distinct type has a zero value if `T` has (§11, Initialization), and a const may hold one if it may hold a `T` (§14). `@fmt` writes it as a `T` unless it has a writer of its own (§13, Formatting).

### C function pointers

<!-- context:
namespace lib {
    capability Lib
    fn lookup { mut lib: Lib, name: []u8 } -> ?*u8 { return null }
    #c::symbol{ name = "ctx_doc_sub" }
    #pure
    extern fn sub { a: i32, b: i32 } -> i32
}
fn main {} {}
-->
```ctx
type Op = extern fn{ a: i32, b: i32 } -> i32

fn call { mut lib: lib::Lib } -> i32 {
    let some{ value = p } = lib::lookup{ &lib, name = "add\0" } else { return 1 }
    let add = @cast(Op, p)                    // the address is a C function of this type
    let n = add{ a = 2, b = 3 }
    let sub: Op = lib::sub                    // a named extern fn: its C symbol's address
    return n + sub{ a = 3, b = 2 }
}
```

1. `extern fn{C} -> R` is a pointer to a C function, as C's `R (*)(...)`: 8 bytes, never null. Its fields are C's parameters in the order they are written, so two such types are the same only if they have the same fields, in the same order, with the same names, types and mutability, and the same result.
2. Its fields and result follow an extern fn's rules (§18): only types with C equivalents, a capability field isn't passed, and a `mut` field passes a pointer.
3. It is called like any function (§3), with every field supplied; it can't be bound (§4). As a capability's field, it can only be called, through the capability (§15, rule 7).
4. A value comes from `@cast(extern fn{C} -> R, p)`, for a pointer `p` (§13), from a named extern fn where that type is expected (the address of its C symbol), or from a named `#c::callback` fn there (a C function that calls it, §18 Callbacks). `@cast(*U, f)` gives the address back.
5. A ctxlang function value (`fn{C} -> R`) doesn't convert to an extern fn type, nor the other way. Only a callback's name does, as rule 4 says.
6. `?extern fn{C} -> R` is a C function pointer that may be `NULL`, as `?*T` is (§8, Optional, rule 6).
7. It holds no addresses of places: as a `fn` value, it may be stored and returned anywhere.

### Untagged unions

<!-- context:
struct Color { r: f32, g: f32, b: f32, a: f32 }
struct DepthStencil { depth: f32, stencil: u32 }
fn main {} {}
-->
```ctx
extern union ClearValue { color: Color, depth_stencil: DepthStencil }

fn depth_of {} -> f32 {
    let v = ClearValue{ color = Color{ r = 1.0, g = 0.0, b = 0.0, a = 1.0 } }
    return v.depth_stencil.depth          // the same bytes, read as another field
}
```

1. `extern union Name { field: T, ... }` declares C's union: every field starts at offset 0. Its size is its largest field's, rounded up to its largest alignment, and its alignment is its largest field alignment, as in C. It can't have generic parameters.
2. It has no tag, so it can't be matched (§8, Match) or taken apart with `let … else`. A field is read and written as a struct's is (`v.color`, `v.color = c`, `p.color` through a pointer), and is a place as a struct field is (§11). Which field holds a meaningful value is for the program to know, as in C: reading a field other than the one last written reads the same bytes as that field's type.
3. A literal sets exactly one field, and the rest of the bytes are zero.
4. Its zero value is every byte zero, if every field type has a zero value (§11, Initialization).
5. A const can't hold one (§14).
6. Two fields of one extern union are the same place for §3.1: `&v.color` and `&v.depth_stencil` given to `mut` fields of one call overlap, an error unless the callee uses them apart (§3.1, rule 8). A value read from a field is derived from whatever the union is (§14).
7. For a union of the language's own, which says which variant it holds, use `union` (§8).

### Slices

A slice is a view of `len` consecutive `T`s that it doesn't own. Slices are built in because they are a shape of memory, like arrays and pointers; what to do with memory (allocating, growing, hashing, text) is left to the standard library.

1. `s.len` is the number of elements, a `usize`. `s.ptr` is a `*T` for a `[]T` and a `*mut T` for a `[]mut T`, pointing to the first element. Neither is a place. The `ptr` of an empty slice is unspecified and must not be dereferenced, except a string literal's view, whose `ptr` points to its hidden zero (§11, Literals).
2. `s[i]` is the element at `i`, bounds-checked: an `i` below 0, or `i >= s.len`, panics. `i` is an integer of any type, as for an array (Arrays, rule 1). It is a place through a deref (§11), mutable only for a `[]mut T`. `(s.ptr + i).*` is the same element without the check; `s.ptr[i]` is an error (Pointers, rule 5).
3. `s[lo..hi]` is the slice of elements `lo` up to but not including `hi`, of `s`'s type. `lo` defaults to 0 and `hi` to `s.len`, so `s[..]` is `s`. `lo > hi` or `hi > s.len` panics, and so does a bound below 0 (`range -1..2 out of bounds for length 3`). `lo` and `hi` are integers of any type, each its own, as an index is (Arrays, rule 1).
4. `a[lo..hi]` on an array place `a` means `(&a)[lo..hi]`, and on a `*[N]T` or `*mut [N]T` it slices the array it points to. The result is `[]mut T` if the place is mutable (§11), `[]T` otherwise.
   - An array const, or an array reached by fields and array indexes from a const, may also be sliced. The result is always `[]T`, backed by immutable static storage (§14), with the same bounds checks. No array is copied to make the view. This does not make the const a place: `&C` and `&C[i]` remain errors.
   - An array literal where a `[]T` is expected is a view of its array, in static storage or in a hidden local (§11, Literals, rule 4).
5. `@slice(p, n)` makes the slice of `n` elements starting at pointer `p` (§13). It isn't checked: it is one of the unchecked operations (§13).
6. Two slices compare with `==` by their contents, their lengths and then their elements, where the element type has `==` (§11, Expressions, rule 5), and `@hash` hashes them the same way (§13, Hashing). Whether two slices are the same memory is a comparison of their `ptr`s and `len`s.

## 13. Builtins

1. A name starting with `@` is a compiler builtin. User code can't declare such names.
2. `@name(...)` is always a builtin call, never generic application (§9). The parentheses are required, even with no arguments.
3. Each builtin has the signature below. Type arguments always come before value arguments, so the builtin's name alone says whether each argument is parsed as a type or an expression. Only `@fmt` takes any number of arguments.
4. An unknown builtin, or a call with the wrong number of arguments, is a syntax error.
5. The type argument of `@as`, `@trunc`, `@cast`, `@round`, `@saturate` or `@round_saturate` may be `_`: the type expected where the call appears (§11 Literals), or its payload if that is optional. In `Gl1_1{ clear = @cast(_, p) }` it is the field's type, and in `let n: i32 = @as(_, big)` the local's. It is an error where nothing expects a type, as in `let n = @as(_, big)`. `_` is a type nowhere else.
6. What earns a builtin: it takes a type or a field's name as an argument (`@size_of(T)`, `@offset_of(T, f)`, `@as(T, x)`); or it needs what only the compiler knows, as a type's layout, the source's text or position, a format string checked while compiling, or a bound function's record (`@panic`, `@expect`, `@require`, `@fmt`, `@record_size`); or it is an unchecked primitive (`@cast`, `@slice`); or it is an arithmetic operation in call form whose operands widen as an operator's do (`@min`, `@max`, `@clamp`). An operation on two operands with an operator's rules is an operator instead (`<<%`, §11), and everything else is a function in std (§17).

| Signature | Result | Meaning |
|---|---|---|
| `@size_of(T)` | `usize` | The size of `T` in bytes. |
| `@align_of(T)` | `usize` | The required alignment of `T`. A power of two. |
| `@offset_of(T, f)` | `usize` | The offset in bytes of field `f` of struct `T` from its start, as C's `offsetof`: 0 for an extern union's. `f` is a field's name. |
| `@as(T, x)` | `T` | Converts number `x` to numeric type `T`. To an integer type it panics if the value isn't representable in `T`, unless an `ifoverflow` covers it (§11, Overflow): a float rounds toward zero first, and NaN and the infinities never are. To a float type it never panics, and no `ifoverflow` covers it: an integer and an `f64` round to the nearest value of `T`, an `f64` past `f32`'s range gives an infinity of its sign (`@as(f32, 1e300)` is `inf`), and NaN stays NaN; `math::is_finite` tells. Also converts between an enum and an integer type (§12, Enums), and between a distinct type and its base, at no cost (§12, Distinct types). |
| `@trunc(T, x)` | `T` | Converts integer `x` to integer type `T`, keeping the low bits. |
| `@cast(*U, q)`, `@cast(*mut U, q)`, `@cast(extern fn{C} -> R, q)` | the target | Reinterprets `q`, a pointer or a C function pointer (§12), as a pointer or a C function pointer. Unchecked, except that a `*T` can't be cast to a `*mut U`, and `q` can't be optional: check it for `null` first. |
| `@slice(p, n)` | `[]T`, or `[]mut T` for a `*mut T` | The slice of `n: usize` elements starting at pointer `p: *T`. Unchecked. |
| `@addr(q)` | `usize` | The address of pointer `q` as an integer. |
| `@hash(x)` | `u64` | A hash of `x` that equal values share, for any type with `==` that holds no float (Hashing, below). |
| `@min(a, b)`, `@max(a, b)` | the operands' one type | The smaller, or the larger, of two numbers (Smallest, largest and clamped, below). |
| `@clamp(x, lo, hi)` | the operands' one type | `x`, or `lo` if `x` is below it, or `hi` if `x` is above it. Panics unless `lo <= hi`. |
| `@round(T, x)` | `T` | Float `x` as integer type `T`, rounded to the nearest integer, a halfway case to the even one. Panics if that isn't representable in `T`, as `@as` does, unless an `ifoverflow` covers it (Rounding and saturating conversions, below). |
| `@saturate(T, x)` | `T` | Number `x` as integer type `T`, a float rounded toward zero as `@as` rounds it, but the nearest value of `T` where `@as` would panic: `T`'s minimum below its range, its maximum above, and 0 for NaN. Never panics. |
| `@round_saturate(T, x)` | `T` | Float `x` as integer type `T`, rounded as `@round` rounds and clamped as `@saturate` clamps. Never panics. |
| `@panic()`, `@panic("reason")` | none | Stops the program. Never returns. It ends a path for return and assignment checks. The reason must be a string literal. The program's `#panic` fn reports it with the panic's location (§15, Entry point), so no capability is needed. |
| `@fmt(b, "format", args...)`, `@fmt("format", args...)` | `!`; a writer | Writes text into a sink, now or when called (below). |
| `@expect(t, c)` | `bool` | A test's check (Checks, below): `c`, a condition, after a failure is reported through `t`, a `*mut Test`, if it doesn't hold. |
| `@require(t, c)` | nothing | A check that a test can't go on without (Checks, rule 6): as `@expect(t, c)`, and the test ends there if `c` doesn't hold. A statement. |
| `@atomic_load(p, order)` | `T` | The `T` that `p: *T` (or `*mut T`) points to, read atomically (Atomics, below). |
| `@atomic_store(p, value, order)` | none | Stores `value` through `p: *mut T` atomically. |
| `@atomic_exchange(p, value, order)` | `T` | Stores `value` through `p: *mut T` and gives the value it replaced, in one step. |
| `@atomic_compare_exchange(p, expected, desired, order)` | `?T` | Stores `desired` through `p: *mut T` if it holds `expected`, in one step: `null` if it stored, else the value it found. |
| `@atomic_add(p, value, order)`, `@atomic_subtract(p, value, order)` | `T` | Adds `value` to, or subtracts it from, the integer `p: *mut T` points to, in one step, wrapping as `+%` does; gives the value before. |
| `@fence(order)` | none | Orders the memory accesses around it as `order` says, without one of its own. |
| `@record_size(run)` | `usize` | Only in a `#starts_task` fn, of its own `run`: the size of the task's record (§15, Tasks, rule 5). |
| `@record_copy(run, into)` | `fn{ record: *mut u8, result: *mut u8 }` | Only in a `#starts_task` fn: copies its own `run`'s record into `into`, a `[]mut u8`, and gives the fn that runs the copy (§15, Tasks, rule 5). |

### Hashing

<!-- context:
fn main {} {}
-->
```ctx
struct Cell { x: i32, y: i32 }

fn slot_of { cell: Cell, buckets: []u32 } -> u64 {
    return @hash(cell) % buckets.len                               // equal cells, equal hashes
}
fn cells { mut heap: arena::Arena } {
    let mut seen = map::make(Cell, bool){ realloc = arena::alloc, &heap }   // std's map hashes its keys this way
}
```

1. `@hash(x)` is a `u64` for a value of any type that has `==` (§11, Expressions, rule 5) and holds no float. Two values that are `==` have the same hash: that is what it is for. It is derived as `==` is, from the parts `==` compares and no others, so it never reads padding, a slice is hashed by its length and its elements, and a pointer, which has `==` only at the top, by its address.
2. A float has no `@hash`, alone or inside a value: a NaN equals nothing, itself included, so a key that held one could never be found again, and `-0.0 == 0.0` though their bits differ. The error names the part and says to hash the bits, which `math::f32_to_bits` and `f64_to_bits` give: equal bits are equal, a NaN's too.
3. The hash depends only on the value: it is the same in a const (§14), under `ctxc interp` and in the compiled program, and in every run. It is not a format: another version of ctxc may compute another, so it isn't stored in a file. It is FNV-1a's step over the parts as 64-bit words, a slice's length before its elements and a union's variant before its fields, then stirred so that every bit depends on all of them; good for a table, not against an attacker who chooses the keys.
4. In a generic function `@hash` takes a value whose type has a parameter in it, as `==` does, and each use of the function must give the parameter a type with `@hash`. So std's `map::make(K, V)` (§17) keys a map by any such `K` without a function written for it; `map::new` takes the caller's hash and equality instead.

### Smallest, largest and clamped

<!-- context:
struct Line { width: i32 }
fn sizes { want: usize, buf: []u8, at: usize, widest: i32, line: Line, level: i32, delta: i32, t: f64 } {
    ...
}
fn main {} {}
-->
```ctx
let n = @min(want, buf.len - at)                  // the smaller of two usizes
let widest = @max(widest, line.width)
let level = @clamp(level + delta, 0, 100)         // 0 if below, 100 if above
let t = @clamp(t, 0.0, 1.0)
```

1. `@min(a, b)` and `@max(a, b)` take two numbers, integers or floats, of one type after widening, as the operands of `<` do (§11, Expressions, rule 1): an `i32` and a `u8` are compared as `i32`s, an integer literal takes the other operand's type, and a const's name converts where its value fits (§11, Widening, rule 7). Two types neither of which widens to the other, as `i32` and `u32` or an integer and a float, are an error: convert one with `@as`. The result has that one type, a distinct type's included (§12). Enums, pointers and `bool` have no order (§12, Enums).
2. Each operand is evaluated once, `a` first. Where the two are equal the result is `a`.
3. For floats, if either operand is NaN the result is NaN, so a NaN isn't lost in a chain of them; C's `fmin` and `fmax`, which give the other operand instead, are `math::fmin` and `math::fmax` (§17). `-0.0` and `0.0` are equal, so `@min(-0.0, 0.0)` is `-0.0`, the first, and `@max(-0.0, 0.0)` is too.
4. `@clamp(x, lo, hi)` takes three numbers: each of `lo` and `hi` pairs with `x` as rule 1's operands do, and all three are converted to the wider of the two types that gives, which is the result's. They are evaluated once, in that order. The result is `lo` if `x < lo`, `hi` if `x > hi`, and `x` otherwise, so a NaN `x` gives NaN and `@clamp(-0.0, 0.0, 1.0)` is `-0.0`.
5. `@clamp` panics unless `lo <= hi`, with `@clamp: the low bound is above the high bound`, and for floats, where a NaN bound fails that test too, `... or one of them is NaN`. Two integer literals out of order are an error while compiling, which says to swap them.
6. They are written with comparisons, so they cost what the `if` by hand costs, give the same value in a const (§14), and never call the C library.
7. They are builtins, though a generic function can order two values of its `T` (§9, rule 6), because their operands widen as an operator's do, either one to the other: the arguments of a generic function's `T` have the type of the first of them, and the rest must widen to it. As builtins they also report two literal bounds out of order while compiling, and a panic gives the line of the `@clamp`, not one in std. For a type without an order, std's `cmp::min_by` and `cmp::max_by` take the order as a function (§17).

### Rounding and saturating conversions

<!-- context:
fn convert { x: f64, r: i32, noise: i32, out: []mut i16, i: usize, sample: f64 } {
    ...
}
fn main {} {}
-->
```ctx
let step = @round(i32, x * 16.0)                  // nearest; panics past i32, as @as would
let px: u8 = @saturate(_, r + noise)              // an i32 clamped to 0..=255
out[i] = @round_saturate(i16, sample * 32768.0)   // rounded and clipped, never a panic
```

`@as(T, x)` to an integer type rounds a float toward zero and panics if the value isn't representable. These three round to the nearest integer, or give the nearest value of `T` instead of panicking, or both:

| | toward zero | to nearest, a half to even |
|---|---|---|
| panics, or `ifoverflow` | `@as(T, x)` | `@round(T, x)` |
| clamps to `T`'s range | `@saturate(T, x)` | `@round_saturate(T, x)` |

1. `T` is an integer type: not a float type, an enum or a distinct type. `x` is an `f32` or an `f64` for `@round` and `@round_saturate`, where an integer is an error that names `@as` and `@saturate`; `@saturate` takes an integer of any type as well.
2. **Rounding** is to the nearest integer, and a value halfway between two goes to the even one: 0.5 gives 0, 1.5 and 2.5 give 2, -0.5 gives 0, -2.5 gives -2. It is IEEE 754's default rounding, what a float operation itself does, and unlike `math::round`, C's, which takes halfway cases away from zero. An `f32` is rounded as the `f64` of the same value, so nothing is rounded twice.
3. `@round(T, x)` then converts as `@as` does: a result that isn't a value of `T` panics with `@as`'s message (`@as: 3000000000.0 is not representable in i32`, which shows the rounded value), and NaN and the infinities always do. An `ifoverflow` covers it as it covers `@as` (§11, Overflow).
4. **Saturating** gives the nearest value of `T`. For a float: 0 for NaN, `T`'s maximum for a value above it and for the infinity, `T`'s minimum for a value below it and for the negative infinity (0 for an unsigned `T`), and otherwise the value rounded toward zero by `@saturate`, as `@as` rounds, or to nearest by `@round_saturate`. For an integer: `T`'s minimum or maximum where `x` is outside its range, `x` otherwise. `@saturate(u8, 300)` is 255, `@saturate(u8, -3)` is 0, and `@saturate(i64, x)` of a `u64` above `i64`'s maximum is that maximum.
5. The saturating conversions never panic and overflow nothing, so an `ifoverflow` doesn't cover them and one over them alone is an error (§11, Overflow, rule 4).
6. All three give the same value while compiling (§14) and when the program runs, and call no C function: rounding is two float additions, which round as rule 2 says in every float operation.
7. They are builtins because no generic function (§9) could be written for them. Of its parameter `T` a function may ask only `==`, `@hash` and an order (§9, rule 6), and these need more: a conversion to `T`, where `@as(T, x)` takes a numeric type and a parameter isn't one; `T`'s smallest and largest values, which nothing names; and for `@round` an `ifoverflow` at the call, which covers operations written before it and never what a called function does (§11, Overflow, rule 1).

### Formatting

<!-- context:
type Heap = arena::Arena
struct Span { at: u32 }
struct Checker { heap: *mut Heap, errors: u32 }
fn message { c: Checker } -> utf8::Builder(Heap) { return utf8::builder{ realloc = arena::alloc, heap = c.heap } }
fn error { mut c: Checker, at: Span, msg: utf8::String } { c.errors = c.errors + 1 }
namespace date {
    struct Date { year: u32, month: u32, day: u32 }
    fn write_iso { mut b: utf8::Builder(arena::Arena), d: Date } -> ! { return @fmt(&b, "{}-{:02}-{:02}", d.year, d.month, d.day) }
}
fn main {} {}

fn errorf { mut c: Checker, at: Span, msg: utf8::Fmt(Heap) } {
    let mut b = message{ c }
    try! msg{ &b }
    error{ &c, at, msg = utf8::view{ b } }
}
fn report { mut io: Io, mut c: Checker, mut b: utf8::Builder(Heap), at: Span, line: u32, col: u32, msg: []u8, name: []u8, kind: []u8, count: u32, flags: u32, ratio: f64, d: date::Date, mark: u32 } -> ! {
    ...
}
-->
```ctx
try @fmt(&b, "{}:{}: error: {}", line, col, msg)                    // write into b now
errorf{ &c, at, msg = @fmt("no variant `{}` in {}", name, kind) }   // a writer, passed on
_ = @fmt(&io, "{:<16}{:>8}  {:08x}  {:.3}\n", name, count, flags, ratio)   // specs (rule 8)
_ = @fmt(&b, "due {} at {}", date::write_iso{ d, _ }, utf8::write_char{ c = mark, _ })
```

A function that takes a writer calls it with its sink, and a `#write` fn writes a type of the program's own:

<!-- context:
type Heap = arena::Arena
struct Span { at: u32 }
struct Checker { heap: *mut Heap, errors: u32 }
fn message { c: Checker } -> utf8::Builder(Heap) { return utf8::builder{ realloc = arena::alloc, heap = c.heap } }
fn error { mut c: Checker, at: Span, msg: utf8::String } { c.errors = c.errors + 1 }
namespace date {
    struct Date { year: u32, month: u32, day: u32 }
    fn write_iso { mut b: utf8::Builder(arena::Arena), d: Date } -> ! { return @fmt(&b, "{}-{:02}-{:02}", d.year, d.month, d.day) }
}
fn main {} {}

-->
```ctx
fn errorf { mut c: Checker, at: Span, msg: utf8::Fmt(Heap) } {
    let mut b = message{ c }
    try! msg{ &b }                                                  // a writer writes when called
    error{ &c, at, msg = utf8::view{ b } }
}

namespace geo {
    struct Point { x: i32, y: i32 }

    #write
    fn write_point(S) { mut b: utf8::Builder(S), p: Point } -> ! {  // how a Point goes into a Builder
        return @fmt(&b, "({}, {})", p.x, p.y)
    }
}
```

1. `@fmt(b, "format", args...)` writes text into the **sink** `b`: any expression of type `*mut B`, for a type `B`, evaluated once. `@fmt("format", args...)`, without a sink, is a **writer**: a bound function (§6) that writes the same text into the sink it is called with. Its type is the type expected where it appears (§11, Literals), which must be a function type with exactly one `mut` field, of type `B`, and a bare `!` result, as std's `utf8::Fmt(S)` is: `&fn{ mut b: Builder(S) } -> !`. Without one, as in `let w = @fmt(...)`, it is an error. A format is always a string literal and a sink never is, so the first argument says which form a call is. `@fmt(b, ...)` writes what `@fmt(...)` would, called on `b` at once, without making a bound function.
2. The format must be a string literal of valid UTF-8. Its text is written as it is, except for holes, which take the remaining arguments in order; their numbers must match. A hole is `{}`, or `{:spec}` with a spec that says how its value is laid out (rule 8). `{{` and `}}` stand for `{` and `}`.
3. The arguments are evaluated once, at the `@fmt`, in order. A writer copies them as a bind does (§4), and holds what they hold: the places their bound functions hold (§3.1), and what they are derived from (§14), so it can't outlive any of them. With a sink first, the sink and the places the arguments' bound functions hold are one call's mut references (§3.1): `@fmt(&b, "{}", w{ &b, _ })` is an error.
4. A fn with the attribute `#write` is a **writer** of its value to its sink. Its context is two fields: the sink, `mut`, and the value, read-only. Its result is a bare `!`, or nothing, for a writer that records failure itself. It may be generic, but neither field's type is a bare type parameter, the value isn't a function, and every type parameter appears in a field's type. The compiler declares `write`, as it declares `convert` (§18, Attributes). An `@fmt` sees the writers its code could name, as a literal sees conversions (§18, Literal conversions, rule 4). For each piece it looks at the program's writers first, and at std's only if it sees none of the program's, so a program's writer replaces std's for the same types, as its names shadow std's (§10).
5. Each piece of the format is written to the sink, a `B`, by the writer the `@fmt` sees for `B` and the piece's type:
   - text is a `strlit` (§12), and so is a string literal argument;
   - an argument of type `T` is written by the writer for exactly `T`. There's no widening, since a `u32` widens to both an `i64` and a `u64`, except two: a `[]mut T` with no writer of its own is written by that of `[]T`, and a distinct type with none by that of its base (§12, Distinct types). The types are those the body settles, after integer literals take their defaults (§11, Literals);
   - a function value whose context is one `mut` field, of type `B`, and that returns a bare `!` is called with the sink. This is how a value is written some other way than a spec says: `utf8::write_char{ c, _ }` and `date::write_iso{ d, _ }` bind everything but the sink (§4). An `@fmt` without a sink as an argument is written as part of the outer one;
   - an error (§8, Errors) is written by the compiler: its full name, as a `strlit`, and its payload as `{ field = value, ... }`, each value by the writer for its type, or without one by its derived text (rule 10): `parse::bad_digit{ at = 3 }`.

   A piece with no writer is an error naming both types; an enum converts to an integer with `@as`, and a `?T` gives a value with `ifnull`. Two writers for the same types, both the program's or both std's, are an error naming both, as two conversions are (§18).
6. The result, of `@fmt(b, ...)` or of calling a writer, is a bare `!` (§8, Errors): `ok` if every piece was written, or the error of the first that failed, after which the sink holds the pieces before it. With a sink first, it fails with the errors of the writers it uses: a set of its own, inferred as a function's is (§8, Errors, rule 5), with an argument that is a function adding its type's declared set, or any error if it declares none. A writer's result is its type's, a function type's `!`, which may hold any error, or `E!`, a declared set that must hold the writers' errors (§8, Errors, rule 14). Like any call's result it must be used (§11.6), and `try @fmt(...)` is a statement as `try` of a call is.
7. `@fmt` is short for the writer calls it stands for, each run only if the one before it succeeded. With a sink first it has no cost beyond them; a writer is a bound function, whose record holds the arguments.
8. A **spec** lays out an integer, a float or a string in a hole:

   ```text
   hole      := '{' '}' | '{' ':' spec '}'
   spec      := [align] ['0'] [width] ['.' precision] [base]     // in this order, and not empty
   align     := '<' | '>' | '^'
   width     := 1 to 255, in decimal, without a leading 0
   precision := 0 to 30, in decimal
   base      := 'x' | 'X' | 'b' | 'o'
   ```

   | Spec | Value | Written |
   |---|---|---|
   | `{:>8}`, `{:8}` | 42 | `      42` |
   | `{:<8}`, `{:^8}` | 42 | `42      `, `   42   ` |
   | `{:<8}`, `{:8}`, `{:>8}` | `"abc"` | `abc     `, `abc     `, `     abc` |
   | `{:06}` | -42 | `-00042` |
   | `{:x}`, `{:X}`, `{:08x}`, `{:b}`, `{:o}` | 255 | `ff`, `FF`, `000000ff`, `11111111`, `377` |
   | `{:.3}`, `{:.0}`, `{:8.2}`, `{:08.2}` | 3.14159 | `3.142`, `3`, `    3.14`, `00003.14` |

   - `width` is the least number of characters the hole writes. A shorter value is padded with spaces, at its right for `<`, its left for `>`, both sides for `^` (the odd one at the right); without one of these a number is at the right and a string at the left. A longer value is written whole. A string's characters are its bytes that don't continue a UTF-8 sequence, so a valid string's code points.
   - `0` pads a number with zeros instead, between its sign and its digits. It needs a width, and takes no alignment. An infinity and a NaN are padded with spaces.
   - `.precision` writes a float with that many digits after the point and never in exponent form, rounded to the nearest such number, a value exactly halfway to the even digit: `{:.1}` of 0.25 is `0.2`, and of 0.35, which as a float is a little under, `0.3`. Without digits there is no point: `{:.0}` of 2.5 is `2`. The sign is the value's, so `{:.2}` of -0.001 is `-0.00`. An infinity and a NaN are `inf`, `-inf` and `nan`.
   - `x`, `X`, `b` and `o` write an integer in hexadecimal, with `a` to `f` or `A` to `F`, in binary or in octal, without a prefix. A negative integer is written as the bits of its type, so `{:x}` of an `i8`'s -1 is `ff` and of an `i32`'s `ffffffff`.
   - The argument is an integer, an `f32` or `f64`, or a string: a string literal, a `[]u8` or `[]mut u8`, or a `utf8::String`; or a distinct type over one of these (§12). A width and an alignment apply to all of them, `0` to the numbers, a precision to the floats and a base to the integers. Any other spec, and a spec on any other argument (a `bool`, an error, a function, an `@fmt`, a type with a writer of the program's), is an error that says which part doesn't apply and what to write: ``` `{:.2}` has a precision, which is a float's digits after the point, and this argument is an i32: drop the precision, or convert the argument with `@as(f64, ...)` ```. A spec that isn't one is an error that gives the grammar; `{:0}` and `{:<08}` have errors of their own, and so has a `{x}`, which says a spec comes after a colon.
   - A hole with a spec is written by the sink's writer of one of std's types (§17, `fmt`), each a struct of the value and its `fmt::Spec`: `fmt::Int` for a signed integer (its value as an `i64`), `fmt::Uint` for an unsigned one and for any integer in another base (as a `u64`), `fmt::F64`, `fmt::F32`, and `fmt::Text` for a string (its bytes). The writer is found as any is (rule 5), so std's sinks have specs, and a sink of the program's own has them once it has writers of these types, each one call of `fmt`'s functions. Without one it is an error: ``@fmt has no writer of fmt::Int to Line, which writes `{:>8}` ``.
9. **A float's text**, as std's writers write an `f32` or `f64` in a hole without a precision: the shortest decimal digits that read back as the same value of its type (`utf8::parse_f32` or `parse_f64`), so an `f32`'s 0.1 is `0.1`. A value from 1e-4 up to, not including, 1e16 in size is written plainly with a point, and a whole number ends in `.0`: `100.0`, `0.001`, `1234567.0`, `-2.5`. Outside that it is in exponent form, a digit, the others after a point if there are any, `e`, a sign and at least two digits: `1e+16`, `1.5e-05`, `3.4028235e+38`. Zero is `0.0` or `-0.0`, and the rest are `inf`, `-inf` and `nan`. It is Python's `repr` of a float, for an `f32` over its own digits. The text is one C function's (`ctxc/rt/ctxfloat.c`) in a compiled program and under `ctxc interp`, so the two agree; a const can't write a float (§14, rule 1).
10. **Derived text.** Where the compiler writes a value itself, a field of an error's payload (rule 5), the error an entry point or a test returns (§15, Entry point, rule 4; §20) or a side of an `@expect`'s or a `@require`'s comparison (Checks, below), a value whose type has no writer is written from its parts, each by the writer the `@fmt` sees for the part's type to the sink, or from the part's own parts:

    | Type | Written | |
    |---|---|---|
    | a struct | `geo::Point{ x = 1, y = 2 }` | its name with its namespaces and without generic arguments, then its fields in order; `Empty{}` without fields |
    | a union | `Shape::circle{ r = 1.5 }`, `Shape::none` | its name, the variant's, and the variant's fields as a struct's; `Shape::dot{}` for an empty payload |
    | an enum | `Color::green` | its name and the variant's |
    | an optional | `null`, or its value | |
    | an array or a slice | `[1, 2, 3]`, `[]` | its elements in order; a `[]u8` has std's writer, and is its bytes as text |
    | a distinct type | as its base | |
    | anything else | `_` | a pointer, which a value's text doesn't follow, a `?*T` that isn't null, a function, a capability, an extern union, and a number, `bool` or string for which the sink has no writer |

    A type with a writer is always written by it, at any depth, so a program's `#write` fn for its `Point` and the sink decides how a `Point` inside an error's payload reads. The writers' errors join the `@fmt`'s set (rule 6), and two writers for one part are an error at the `@fmt`. The text is for a person or a model reading a failure, not a format to parse back: a string is its bytes without quotes. A hole of an `@fmt` itself is not written this way: a value there without a writer is still an error (rule 5), so what a program prints is always what a writer of its own or std's says.

### Checks

<!-- context:
struct Row { name: []u8 }
namespace cfg_tests {
    #test
    fn reads { mut t: Test } {
        let text: []u8 = "seventeen letters"
        let name: []u8 = "x"
        let rows: []Row = []
        ...
    }
}
-->
```ctx
@expect(&t, text.len == 42)                       // cfg.ctx:9: fail: cfg_tests::reads: text.len == 42: 17 == 42
@expect(&t, slice::eq_bytes{ a = name, b = "x" }) // cfg.ctx:10: fail: cfg_tests::reads: slice::eq_bytes{ a = name, b = "x" }
@require(&t, rows.len > 0)                        // cfg.ctx:11: fail: cfg_tests::reads: required: rows.len > 0: 0 > 0
@expect(&t, rows[0].name == "bastila")            // not reached without a row: the test ended at line 11
```

1. `@expect(t, c)` is a test's check (§20): `t` is a `*mut Test`, as `&t` for a test's `mut t: Test`, and `c` a condition, a `bool`. Its value is `c`'s, which may be dropped: `@expect(&t, c)` is a statement too. It never panics and never returns from the function: a check that doesn't hold is noted and written, and the test goes on. A test whose next lines need what was checked uses `@require` (rule 6), not `if not @expect(&t, c) { return }`, which is easy to leave out.
2. If `c` doesn't hold, one line goes to standard error: `FILE:LINE: fail: NAME: TEXT`, where FILE and LINE are the `@expect`'s, NAME is the running test's, and TEXT is `c` as it is written, on one line. If `c` is a comparison, `a == b`, `!=`, `<`, `<=`, `>` or `>=`, the line goes on with `: `, the value of `a`, the operator and the value of `b`: `text.len == 42: 17 == 42`. Each side is evaluated once, the left one first, and the comparison is of those two values, as it would be without the `@expect`. Any other condition, `a and b`, a call, an `is`, has its text alone: to see a value, compare it.
3. A side's value is written by the writer that an `@fmt` at the `@expect` would see for its type to an `io::Stderr`, the program's before std's, or without one by its derived text (Formatting, rule 10): `Point{ x = 1, y = 2 }`, `Kind::char`, `null`, `[1, 2]`. A side that is `null` is written `null`, and a string is its bytes without quotes. Two writers for a side's type are an error. In a generic fn, a side whose type has a parameter in it is written as its type in each instance says.
4. A check is counted through `t`, and one that didn't hold is noted there: a test that makes none fails (§20, rule 3), and the summary of a run says how many its tests made (§20, rule 9). Only code that holds a `Test` can check, so a build that isn't a test build never runs one.
5. It is a builtin because no function could be: the report is of where the check is, of its condition's text and of both sides of a comparison inside that condition, which only the compiler has, and a function is given values, with no position and no source. A function taking the two sides apart, `expect_equal{ &t, a, b }`, would still lack the position, and one for each operator and each shape of condition is the assertion library this replaces. Everything else is std's: the builtin calls `test::check{ &t, held, file, line, text }` (§17, `test`), which counts the check and starts the line, and writes the sides with the `#write` fns any `@fmt` uses.
6. `@require(t, c)` is the check a test can't go on without. It takes what `@expect` takes and checks as it does (rules 2 to 4): one that holds is a check the test made, and nothing more. If `c` doesn't hold, its line is an `@expect`'s with `required: ` before TEXT, `FILE:LINE: fail: NAME: required: TEXT`, with both sides after it for a comparison, and then **the test ends**: nothing after the `@require` runs, whether it is in the test or in a function the test passed its `Test` to. The lines of the test's earlier checks are already written, and it is counted once, as a failed test (§20, rule 3).
7. How a `@require` is used, and what follows it:
   - It is a statement and has no value: `let held = @require(&t, c)` and `if not @require(&t, c) { ... }` are errors. A value could be read and then ignored; `@expect` is the check that has one.
   - The test ends in every build and under every runner, so after the statement `c` held: what `c` narrows when true holds from there to the end of the enclosing block, and the bindings of an `is` in it are declared, as after `if not c { return }` (§8, Optional, rule 5; §8, Is, rule 6). `@require(&t, row != null)` makes a `let row: ?Row` its `Row` in the lines below. The checker knows nothing else from it: the code after a `@require(&t, false)` is checked as code that runs.
   - The test ends by its process ending: std's `test::stop` (§17, `test`) writes out what the thread holds for standard output, and exits with code 1. No `defer` runs, in the test or in its callers (§11, Defer, rule 5), and its tasks aren't waited for. What a test must undo outside its process, such as a file it made, it removes before the `@require`, or leaves for its next run to replace.
   - Under std's runner each test has a process of its own (§20, rule 7): the test ends alone, the runner prints its lines and counts it failed, and the other tests run. A `#test_main` fn that runs tests in its own process with `test::run_here` (§20, rule 11) ends with the test: the line is written, the exit code is 1, and the tests after it don't run.
8. `@require` is a builtin for `@expect`'s reason (rule 5): the same position, text and sides, which no function is given. The rest is std's here too: it calls `test::require{ &t, held, file, line, text }`, which is `test::check` with the word `required: `, writes the sides, and then calls `test::stop{ &t }`, with a `Test` that the compiler supplies as it does a panic fn's capabilities (§15, Entry point, rule 6). A `Test` may end its own test and nothing else: `test::stop` and `test::skip` (§20, rule 5) are the two functions that do.
9. **A check in a function the test called.** A check that doesn't hold says where it is, and that isn't which of the test's calls reached it. So under its line, a check in a function other than the test fn has the calls that led there (§15, Call paths), innermost first, up to the test fn, each as two spaces and `called from NAME (FILE:LINE:COL)`: the function that made the call, and where. A check in the test fn itself has none, and neither has one in a test build without call paths (§15, Call paths, rule 7). The lines follow the shapes of a panic's path: `called from NAME (FILE)` where the position isn't known, `called from C code (no position)`, `started from NAME (FILE:LINE:COL)` for a check in a task on a worker, and `... N more frames` in a long one. std writes them: after the failure's line the builtin calls `test::write_callers{ &t }` (§17, `test`), with a `Test` the compiler supplies, as for `test::stop`.

   ```text
   lib/formats/table_test.ctx:8: fail: twoda_tests::reads_rows: a.cells[i] == b.cells[i]: 3 == 4
     called from twoda_tests::same_row (lib/formats/table_test.ctx:15:9)
     called from twoda_tests::reads_rows (lib/formats/table_test.ctx:31:5)
   ```

### Atomics

<!-- context:
struct Shared { count: u32 }
struct Job { done: u32 }
struct Slot { state: u32 }
fn work { mut threads: Threads, mut shared: Shared, job: *mut Job, mut slot: Slot } {
    ...
}
fn main {} {}
-->
```ctx
let before = @atomic_add(&shared.count, 1, atomic::Order::relaxed)
while @atomic_load(&job.done, atomic::Order::acquire) == 0 { thread::yield_now{ &threads } }
match @atomic_compare_exchange(&slot.state, 0, 1, atomic::Order::acquire_release) {
    null => {}                            // it was 0, and is 1 now
    some{ value } => {}                   // another thread got there first: value is what it found
}
```

1. An atomic reads or writes a `T` through a pointer in one step, which no other thread's access to it divides: an integer type, `bool`, an enum (as its base type), a pointer or a `?*T`. `@atomic_add` and `@atomic_subtract` take an integer type only. Every other access to the same memory while threads share it must be atomic too, or the program has a data race, which is undefined behaviour, as C's.
2. The last argument is the **order**, std's `atomic::Order` (§17): `relaxed`, `acquire`, `release`, `acquire_release` or `sequentially_consistent`, C11's memory orders. It must be a constant: one of its values, or a const of one. A load can't be `release` or `acquire_release`, nor a store `acquire` or `acquire_release`. A failed compare and exchange orders as a load of the same order, without its release.
3. Values are checked as an assignment's: an integer literal takes `T`, and what `@atomic_store`, `@atomic_exchange` and `@atomic_compare_exchange` store can't hold a local's address (§14, Escape check), as a store through a pointer can't.
4. They compile to GCC's `__atomic` builtins, which every C compiler ctxc uses has. The interpreter runs one thread at a time (§17, `os`), where each is the plain read or write.

### Unchecked operations

An operation is checked, while compiling or by a panic when it runs, unless it is one of the **unchecked operations**. Each of those makes a pointer, a slice or a call that the compiler takes on the program's word, and a wrong one is undefined behaviour. This is the whole set; rule 3 lists what can end in undefined behaviour without any one operation being the unchecked one.

| Unchecked | What nothing checks | Checked instead |
|---|---|---|
| `@cast(T, q)` | That what `q` points to is a `T`, or the C function a function of that type. It can forge anything, a capability too (§15, rule 4). | |
| `@slice(p, n)` | That `n` elements follow `p`. | `a[lo..hi]` on an array or a slice (§12, Slices) |
| `q + n` on a pointer | That the result is inside `q`'s allocation, so `(q + i).*` isn't bounds-checked (§12, Pointers, rules 4 and 5). | `s[i]` on an array or a slice |
| `@record_copy(run, into)` | What the fn it gives is later called with: it runs whatever its `record` points to (§15, Tasks, rule 5). | std's `task::start` |
| A `c::String` from a pointer: `c::String{ ptr = p }`, assigning its `ptr`, or `&s.ptr` | That a NUL ends the bytes `p` points to (§18, Extern functions, rule 4). | a string literal, which its hidden zero ends |
| Declaring an `extern fn`, a capability's C variable (`extern name: T`) or a `#c::callback` fn | The declaration against C's, and what C does: its types, its `#pure` or capability, the thread it calls back on (§18). | |
| Declaring an `extern union` | Which field holds a value: reading another reads its bytes as that type, a pointer too (§12, Untagged unions). | a `union`, which says which variant it holds (§8) |

1. A build program can make them errors in an executable's files, but for those in the directories it names: `build::deny_unchecked` (§19, rule 17). Code elsewhere then can't write one, and a review for memory safety reads only those directories. The error is at the operation, or at the declaration's name, and says which checked form to write, where there is one. An executable without that call, and a program without a build program, may use them anywhere. std's files always may: they are the language's own.
2. Only writing one is denied, not using what it made. Denied code may call an extern fn, call a fn that returns a `@slice`, read an extern union's field, and deref a pointer it was handed. The directory that declares or makes these answers for what its callers can do with them: a binding that hands on C's functions as they are hands on their dangers, so where that matters it keeps them behind checked functions.
3. These can also end in undefined behaviour, and are not in the set, because no one operation in the source is the unchecked one. A review looks for them wherever they are:
   - Using memory that is gone: freed through its allocator (§14, rule 3), or reached by a pointer the escape check doesn't follow (§14, Escape check, rule 4). The free and the later use are each checked operations.
   - A data race: memory two threads reach through a pointer or a slice, which must be locked or atomic (Atomics, rule 1; §15, Tasks, rule 9).
   - An allocator of the program's own (§14, rule 3): std's typed allocation trusts it to return memory that nothing else has, aligned and zeroed.
   - A `#start` fn of the program's own that sets no stack limit (§15, rule 13): running out of stack then isn't a panic.
4. `@addr(q)` isn't one: it gives the address as an integer, and nothing makes a pointer from an integer. Nor is `q.*`: a pointer's deref is as good as what made the pointer.

## 14. Memory

1. Static memory holds read-only string literal bytes, with the hidden zero after them (§11 Literals), the immutable backing storage of const array views (§12, Slices) and of array literals' static views (§11, Literals, rule 4), and capabilities' statics (§15, rule 13), the only static memory a program writes, reached only through their capabilities. `const NAME: T = e` declares a constant, whose value is computed while compiling. `e` may be any expression of type `T`, calls included. A const has no context, so it holds no capability (§15), and nothing it runs reaches outside the program. A const is a value, not a place, so `&C` is an error. Slicing an array in a const exposes read-only storage that lives until the program ends. The compiler may duplicate that storage; pointer identity between separately obtained const views is not guaranteed.
   - An `e` made of literals, folded consts, enum values, operators but `ifoverflow` and a value type's `==` and `!=` (§11, Expressions, rule 5), `@size_of`, `@align_of`, `@offset_of`, and struct, union and array literals of these is **folded** before the bodies are checked. What would panic at run time is an error at the operation.
   - Any other `e`, one that uses a const that isn't folded included, is **run** once every body is checked and the error sets are inferred, the first time its value is needed. What stops it is an error at the const: a panic, with its message and position; too many steps, or too deep a recursion; or calling an extern fn (§18), since none can run while compiling but the C library's math functions (§17, `math`).
   - A const whose value needs its own, directly or through the functions it calls, is an error.
   - The value may hold no pointer, slice or function value, except a `[]u8`, a `strlit` or a `*u8` that points into a string literal's bytes (part of them is fine; a `*u8` is followed by the rest of them and the hidden zero), or a struct over one, such as `utf8::String` or `c::String`, or a static view of an array literal (§11, Literals, rule 4) that is folded, or an empty slice of any type, which points to nothing. Const array views may be consumed during compile-time evaluation, but cannot themselves be stored in a const's value: the evaluator does not preserve references to their backing storage in its result.
   - An array length (§12) or an enum's value can use only a folded const: they are needed before anything can run.
2. Locals and context fields live on the stack.
3. Memory not on the stack comes from `mem::pages`, which needs the `Mem` capability (§15), or from an allocator function over memory the caller provides. It is accessed only through pointers and slices.
   - Allocators are byte-level: `alloc::Fn(S) = fn{ mut heap: S, mem: Bytes, new: usize, align: usize } -> ?Bytes`. The result must be aligned to `align`, and its bytes past those it keeps from `mem` must be zero, as memory a program hasn't written is (§11, Initialization), even where the allocator handed them out before.
   - Typed code calls the standard library's `alloc::resize(T, S)`, which passes `count * @size_of(T)` and `@align_of(T)` and casts the result, `alloc::make(T, S)` for `count` new `T`s, each its zero value, or `alloc::new(T, S)` for one initialized `T`. All fail with `alloc::out_of_memory` (§8, Errors) where the allocator returns null, as does everything in std that allocates.
   - Pages are never freed. They live until the program ends.
4. The size of every local is known at compile time.
5. Structs, unions and arrays are values. Assignment and `return` copy them.
6. A `mut` context field is passed as a pointer. A read-only context field is passed by copy or by reference, at the compiler's choice. Either way the callee sees the value the argument had when it was evaluated: §3.1 makes the choice unobservable for checked arguments. Only a change made during the call through a pointer §3.1 doesn't check (rule 6) may be seen by a callee given a reference. A bind always copies (§4).
   - ctxc passes a read-only struct, union or array of more than 32 bytes by reference, to any function but an extern fn (§18), which C passes it to by value. The reference is to the argument's place if it is one and nothing else in the call can change it: no argument after it may call a function or run statements, and no other argument, nor the function value called, holds a pointer that comes from the same local (`&x`, `x[..]`, a pointer `p` for `p.*`, or a bind holding `&x`; any `&fn` local counts). Otherwise it is to a copy made when the argument is evaluated.
7. Stack size is finite. Exceeding it panics where a stack limit is set (§15, rule 13): std's start sets one.

### Escape check

The compiler checks that the address of a local does not outlive it. Direct calls use inferred borrowing summaries; indirect calls remain conservative. This checks stack-local origins, not allocator ownership, arena resets or explicit frees.

1. A **stack pointer** to `L` is `&p` where `p` doesn't go through a deref and its root is `L`, a local or a read-only context field. `&x` for a `mut` context field `x` is not a stack pointer, because it points into the caller.
2. A value is **derived from** `L` if it is a stack pointer to `L`, or is produced from a value derived from `L` by:
   - `let` or assignment
   - a struct, union or array literal, or an error with a payload (`name{ field = e }`)
   - pointer arithmetic, `@cast` or `@slice`
   - converting a `*[N]T` to a slice, slicing (`s[lo..hi]`), or `s.ptr`
   - a `for` (§11, For): the address of its `&x`, from what the loop goes over, as `&s[i]` is; and an element's copy `x`, from what the elements of an array it goes over are
   - a direct call, whose result is derived from the read-only parameters that may flow into that output. Success and error outputs have separate summaries: `try` propagates only error origins and yields only success origins. A fresh copy or static error need not borrow an input that only controls its contents or selection.
   - an indirect call, whose outputs conservatively derive from all read-only arguments and the callee's captured origins; a bind (§4) copies all read-only arguments and the callee's captured origins. Arguments passed to `mut` fields do not count.

   Summaries track parameters as whole values, not individual fields. Reads through pointers and slices preserve their input origins. Pointer-bearing stores through mutable caller storage or dereferences conservatively taint pointer-bearing outputs and propagate through calls, even if a call's result is discarded. Generic store types are substituted at direct calls, so copying bytes does not count as storing pointers. Unknown calls conservatively may store their read-only inputs and captured origins, except that an extern fn or an unbound fn value can store them only into a mutable place it reaches: through a `mut` field, or a `*mut` or `[]mut` in an argument, to a type that can hold a pointer. A lookup through a function-valued `hash` or `eq`, or a C call taking a path, so stores nothing. A generic argument decides at each call whether its type reaches one. Calls inside recursion retain conservative dependencies. Only a declared top-level `!T` result has separate output channels; generic results and projections or aggregates containing errors conservatively merge their origins. Local `!T` values and pattern payloads may also combine success and error origins; no written function type carries a borrowing contract.

   Only values whose type contains a pointer carry this. An error type (§8, Errors) contains one if an error of its set has a payload that does, and a `!T` if its `T` or its error type does. A `&fn` contains one; the places it holds follow §6. A string literal view, a view into const array storage, or an array literal's static view is derived from nothing. An array literal's other views are derived from its hidden local, and from what its elements are derived from (§11, Literals, rule 4).
3. It is a compile error to:
   - `return` a value derived from any local or read-only context field of the function
   - `try e` (§8, Errors) when the error output is derived from a local or read-only context field of the function: `try` may return the error
   - assign a value derived from `L` to a local declared in a scope outside `L`'s
   - assign a value derived from `L` to a `mut` context field or any part of one
   - assign a value derived from `L` to a place that goes through a deref

   While the bodies are checked a function's error set isn't known yet, so a value of its error type is taken to contain a pointer if any error of the program has a payload that does. An error above that only such a set could cause is reported once the sets are inferred, and only if the set has an error whose payload contains a pointer.
4. Not checked: a callee storing a read-only pointer argument through its own `mut` field, and a pointer returned from a `&p` passed to a `mut` field. These remain undefined behaviour if the memory no longer exists (§12).
5. A task's handle is derived from what its task borrows, through `mut` fields too (§15, Tasks, rules 8 and 10).

## 15. Capabilities and the entry point

<!-- context:
namespace gl {
    const COLOR_BUFFER_BIT: u32 = 16384
    fn load_2_0 { get_proc: &fn{ name: c::String } -> ?*u8 } -> ?Gl2_0 {
        let clear = get_proc{ name = "glClear" } ifnull { return null }
        let use = get_proc{ name = "glUseProgram" } ifnull { return null }
        return Gl2_0{ clear = @cast(_, clear), use_program = @cast(_, use) }
    }
}
namespace glfw {
    fn proc_address { mut glfw: Glfw, name: c::String } -> ?*u8 { return null }
}
...
-->
```ctx
capability Glfw                                   // permission to call a C library (§18)

namespace gl {
    capability Gl1_1 { clear: extern fn{ mask: u32 } }                    // permission to call OpenGL: its functions
    capability Gl2_0 { ..Gl1_1, use_program: extern fn{ program: u32 } }  // 1.1's, and those 2.0 added
}

namespace os { capability Proc { extern environ: *?c::String } }   // a C variable, read only in os

fn clear { mut gl: gl::Gl1_1 } { gl.clear{ mask = gl::COLOR_BUFFER_BIT } }  // a call through it

fn main { mut io: Io, mut fs: Fs, mut glfw: Glfw, args: Args } -> i32 {
    let mut gl = gl::load_2_0{ get_proc = glfw::proc_address{ &glfw, _ } } ifnull { return 1 }   // only gl's functions make one
    clear{ &gl }                                  // a Gl2_0 includes a Gl1_1
    return 0
}
```

1. `capability Name` declares a **capability type**: permission to have some effect (§1.3). It has no generic parameters and no zero value. Without fields it takes no space; with them (rule 5) it is a struct of C functions. C variables (rule 12) and statics (rule 13) take no space, and a capability whose only fields are these counts as one without fields.
2. Nothing can construct a capability without fields: `Name{}` is an error. The only ones are those `main` receives, which it passes down to the functions that need them, and those a callback receives when C calls it (§18 Callbacks), on the binding's word that C calls it only while they are held.
3. std declares `Io` (console, §17 `io`), `Fs` (files, §17 `fs`), `Mem` (memory beyond the stack, §17 `mem`), `Proc` (other programs and the environment, §17 `proc`), `Threads` (running tasks and waiting for them, §17 `task`), `Build` (a build program's, §19) and `Test` (a test's checks, §20). A binding of a C library declares its own, and its extern fns with effects take it (§18).
4. A capability is permission for code that follows the rules, not a sandbox: a pointer `@cast` (§13) can forge one, as it can corrupt any memory.
5. `capability Name { field: extern fn{C} -> R, ... }` declares one with **fields**: C functions it holds, such as a library's looked up at run time. Each field is a C function pointer (§12), never null; a `?extern fn` isn't allowed, since unwrapping it would read the field (rule 7). Its layout is a struct's.
6. Only a function declared directly in the namespace that declares it, inside the module that declares it if one does (§10, Modules, rule 8), whose context holds a capability or a bound function (`&fn`, §6), can construct one, with a literal (`Name{ field = f, ... }`, §7). Holding one means that function made it. These are how effects reach a function (§1.3): a bound function may hold a capability, as a loader bound to a library's does (`glfw::proc_address{ &glfw, _ }`), so a binding can take one without naming the library it comes from. Code that holds no capability has none to bind a loader to. A loader that holds none can't look a function up: short of a `@cast` (rule 4), it returns `null` or a named function of the type it returns, which is pure if that type takes no capability (§18).
7. Its fields can only be called: `x.f{ ... }` calls the function field `f` holds, and `x` must be a mutable place, as for passing it to a `mut` field (§3); through a `*mut` to one, `p.f{ ... }` calls it too. Holding `x` is the permission, so the field's type needs no capability field. Reading a field as a value (`let g = x.f`, passing, comparing, casting or taking its address) or assigning one is an error: it would reach code whose signature doesn't name the capability.
8. One may be a local, a function's field, a result or an optional's payload, and copies as a struct does, but is never replaced: assigning to a place that is or holds one, as a field, an element or a payload, is an error, except the one assignment of a `let x: T` (§11, Initialization). So the functions a capability holds never change, and a copy of it is the same as it (rule 10). Neither the runtime nor C can make one, so `main` can't take one (Entry point, rule 2), nor can a callback (§18 Callbacks, rule 4). An extern fn may take one as any capability: it isn't passed to C.
9. `..Name` among a capability's fields **includes** `Name`, a capability with fields: it has `Name`'s fields where `..Name` stands, so through `Name` it has those of what `Name` includes. Its own fields and any number of inclusions may come in any order: `capability MyGl { ..Gl3_3, ..ArbDebug }`. A field reaches a capability only once: one of its own that an included one has, or one that two included ones share, as with both `..Gl3_0` and `..Gl2_0` when `Gl3_0` includes `Gl2_0`, is an error. A static (rule 13) may be reached twice, as `capability App { ..Io, ..Fs }` reaches `task::Cancel`'s through both: it is one for the program already, so nothing is duplicated. So is including itself, directly or not. A capability with fields may include only capabilities with fields: a function of its namespace makes it (rule 6), and could otherwise give away the permission of one that only `main` receives. One without fields may include any capability, as std's `Proc` includes its platform's `os::Proc` (§17).
10. A capability converts implicitly to one it includes, directly or not, wherever §11 Widening rule 1 applies: a copy of the functions they share, which rules 7 and 8 keep from changing. A `mut` field of the included type takes a pointer to the including one (§3, rule 4): `draw{ &gl }` for `draw { mut gl: Gl2_0 }` with `gl: Gl3_3`, which §3.1 treats as any `&gl`. If the included one's fields are the first of its own, as when `..Gl2_0` is the first item of `Gl3_3` or of its first inclusion, the callee gets that pointer; otherwise it gets the address of a copy of them, which no program can tell apart from it, since neither changes. Structs, other pointers and `?A` don't convert this way (§11, Widening, rule 5).
11. In a capability's literal, where rule 6 allows one, `..e` supplies from `e` the fields of `e`'s type, which must be a capability the literal's includes: `Gl3_3{ ..base, vertex_attrib_divisor = @cast(_, p), gen_samplers = @cast(_, q) }`. Every field is still supplied exactly once, by a spread or by name. `e` is evaluated before the other items. `..e` in any other braces is an error.
12. `extern name: T` among a capability's fields declares a **C variable**: the C global `name`, or the one `#c::symbol{ name }` on the line before gives (§18), of a type C stores: a number, `bool`, an enum, a pointer or `?*T`, a struct, an extern union or a C function pointer. The linker supplies it, not a literal, so it takes no space (rule 1). `x.name` reads it, through the capability, one that includes it, or a pointer to either, only in a function declared directly in the namespace that declares the capability, inside the module that declares it if one does (§10, Modules, rule 8). That namespace wraps it for every other caller, as a platform layer wraps `environ` (§17). A read is the variable's value at that moment, which C may change. It isn't a place: it can't be assigned or have its address taken. An including capability has the variables of what it includes, and a name reaches a capability only once, as a field or a variable (rule 9).
13. `static name: T` among a capability's fields declares a **static**: storage for one `T` for the whole program, which starts as `T`'s zero value (§11, Initialization), so `T` must have one. There is one for the program, however many capabilities include it, and it takes no space in them (rule 1): a capability holds no state, since the runtime and C make fieldless ones from nothing (rule 2; §18 Callbacks), but it is the only way to reach some. `static` is a keyword only there, before a name. `x.name`, through the capability, one that includes it, or a pointer to either, is a place, only in a function declared directly in the namespace that declares the capability, inside its module, as for a C variable (rule 12). It is mutable when `x` is: a `mut` field, a `let mut`, or through a `*mut`. A read-only capability reads it, and other capabilities that include it reach the same storage. It is a place through a deref (§3.1, rule 6; §14, Escape check): `&x.name` points to storage that outlives every frame, even when `x` is a local, and the escape check keeps a stack pointer from being stored in it. `#c::symbol` doesn't apply to it. An including capability has the statics of what it includes, and a name reaches a capability only once (rule 9).
    - `#stack_limit` on a `usize` static makes it the **stack limit**: on entry, every function compares its frame's address to it and panics with "stack overflow" below it, with the call path of its caller (Call paths, rule 5). 0, the static's start, checks nothing, and a panic sets it to 0 before the panic fn runs (Entry point, rule 6). Each thread has its own (as `#thread_local`, below): std's start sets the main thread's, and a task's worker sets its own from its stack (§17, `task`); on a thread the program didn't start, which calls a callback (§18, Callbacks, rule 6), it is 0. Its storage is the runtime's, which a program that isn't threaded (Entry point, rule 8) keeps in a plain global. std's `rt::Stack` has one, which std's start sets. A program may declare its own, which replaces std's, only if it has its own start fn too, since std's sets std's; a start fn of a program's own without one leaves std's at 0, so nothing is checked.
    - `#thread_local` on a static gives each thread its own, which starts as `T`'s zero value when the thread does: C11's `_Thread_local`, in a threaded program (Entry point, rule 8). In any other, the program's one thread has the one static, as without it. std's io `out`, standard output's buffer, is one (§17, `io`).

### Tasks

A **task** is a call of a `#task` fn, made by a bind written in a start's call that supplies every field, that may run concurrently with the code that started it. std's `task` (§17) starts and waits for tasks; this section is what the compiler checks of them. How the backend behaves, and the design's reasons, are in internals.md, Tasks.

<!-- context:
struct Buffer { n: usize }
fn main {} {}
-->
```ctx
#task
fn load { mut fs: Fs, path: []u8, into: *mut Buffer } -> !usize {
    let size = try fs::size{ &fs, path }
    into.n = @as(usize, size)
    return into.n
}

fn load_two { mut fs: Fs, mut threads: Threads, a: *mut Buffer, b: *mut Buffer } -> !usize {
    let mut ta: task::Task(!usize)
    let mut tb: task::Task(!usize)
    task::start{ &threads, task = &ta, run = load{ &fs, path = "a.txt", into = a, _ } }
    task::start{ &threads, task = &tb, run = load{ &fs, path = "b.txt", into = b, _ } }
    let na = try task::wait{ &threads, task = &ta }
    let nb = try task::wait{ &threads, task = &tb }
    return na + nb
}
```

1. `#task` on a fn with a body makes it a **task fn**, which a start can run. It is still a fn, which code may call and use as a value. Its context may take any field but a **thread-bound** capability, directly or through a pointer, an optional, a slice or an array: an error at the declaration. A generic task fn's instances are task fns, and a start of one whose generic arguments give it a thread-bound capability is an error at the start.
2. `#thread_bound` on a capability declaration says its library may be used only on the thread that made it, or only on the main thread, as OpenGL's contexts and GLFW are. A capability that includes one is thread-bound. A binding marks what its library's documentation says; the compiler can't check the library. std's `Build` is one: its state isn't for two threads (§19).
3. `#starts_task` on a fn with a body, std's `task::start` and its kin, makes it a **start**: its context has a read-only `run: &fn{} -> R`, the task, and a handle it starts the task into, `mut task` or `mut group`, of a `#task_handle` type. At a call of a start, `run` must be a bind written in the call, of a task fn, supplying every field (`run = load{ &fs, path, into, _ }`): not a function value, a `&fn` local or a bind of one. A start is only called: not bound, and not used as a value. Inside a start, its own `run` may be passed on to another start.
4. `#task_handle` on a struct, std's `task::Task(R)` and `task::Group`, makes it a **handle**. A type that is or holds a handle may be the type of a local, of a local array's elements, or of a `mut` field, and nothing else: not a read-only field, a result, a struct's, union's or error's field, a pointer's target, an optional's payload, or a generic argument but a handle's own. A handle's local is declared without a value, which is its zero value, no task, whether or not the result type has a zero value; it is never assigned or copied, so it doesn't move while its task writes its result into it.
5. Inside a start, `@record_size(run)` is the size of the record of the bind passed as its own `run`, a `usize`, and `@record_copy(run, into)` copies it into `into`, a `[]mut u8` at least that long and aligned for any record (shorter panics), and gives a `fn{ record: *mut u8, result: *mut u8 }` that runs the copy found at `record` and writes what it returns to `result`, a place of `R`. This is what a backend keeps of a task while its starter goes on. Nothing else may use them.
6. **A handle's scope ends its tasks.** When the scope of a local that is or holds a handle ends, by any path (falling through, `return`, `try`, `break`, `continue`), each task it still has is cancelled and waited for, its result dropped, as if `defer task::end{ &threads, task = &handle }` (or `task::cancel_all` for a group, each element for an array) followed its declaration: after the scope's later defers, before its earlier ones. The `Threads` this takes is made from nothing, as a capability without fields is (rule 1). A `wait` or `cancel` of a local handle that holds no task on any path to it, and a start into one that holds a task on every path to it, are errors. A loop forgets what it knows of a handle declared before it.
7. **What a task borrows.** A start's bind holds each place it takes as `&p` for a `mut` field (§3.1), capabilities aside, and **reads** each local its read-only arguments are derived from (§14, Escape check). These are the task's **borrows**, its **loan**, which lasts until its handle is waited on or cancelled (`task::wait`, `cancel`, `end`, and for a group `wait_all` and `cancel_all`) on every path, or the handle's scope ends. A handle that is an array's element is ended by its scope only: which element a wait names isn't known.
8. **The handle can't outlive them.** A local handle must be declared in a scope within each borrowed local's scope. A handle that is a `mut` field is the caller's: its task may borrow only what the caller passed, through `mut` fields.
9. **What a running task borrows is its own.** While a loan lasts, the function can't use a place it holds (read, write, take its address, or pass it), and can't write, or pass to a `mut` field, a local it reads. It may still read those. Capabilities are shared: two tasks may each hold `&fs`, and the starter may keep using `fs`. As elsewhere (§3.1, rule 6; §14, rule 4), places through a pointer or a slice aren't checked: memory reached that way is shared as threads share it, under a mutex or with atomics.
10. **Through `mut` fields.** A function that starts a task into a handle it got through a `mut` field, or waits on or cancels one, says so in a summary its callers apply at each call: which of its fields the tasks it leaves in the handle hold and read, and whether it ends the handle on every path. A caller's loan then holds and reads what it passed to those fields, as if it had started the task itself, and rules 8 and 9 hold for it. So `audio::start{ &dev, &mixer }` holds the caller's `dev` until `audio::stop{ &mixer }`.
11. The compiler checks rules 7 to 10 once the bodies are checked, by a walk over each function that touches tasks in evaluation order; a loop is walked until what may reach its start stops growing. A defer's body is checked where it is written, with the loans live there: it may run at an early exit while they still are.

### Entry point

1. `fn main { ... }` is the entry point.
2. Every field of `main` must have a capability type without fields (C variables and statics don't count, §15 rules 12 and 13), except a read-only field `args`. The runtime supplies them. A program declares only the ones it uses.
3. `args: Args` holds the command-line arguments that follow the program, as bytes. `Args` is a top-level std alias for `[][]u8` (§17), so either spelling is accepted.
4. `main` may return `i32`: the program's exit code. Without a return type it exits with 0. It may also return `!` or `!i32` (§8, Errors), so that a small program passes a failure up with `try`: `ok` exits with its value, or with 0 for a bare `!`; an error is written to standard error, after what standard output holds, as `error: ` and the error with its payload and a line break, and the program exits with 1:

   ```ctx
   error empty{ path: []u8 }

   fn main { mut fs: Fs, args: Args } -> ! {
       let size = try fs::size{ &fs, path = args[0] }       // writes error: fs::not_found
       if size == 0 { return empty{ path = args[0] } }      // writes error: empty{ path = notes.txt }
   }
   ```

   The error is written as an `@fmt(&e, "error: {}\n", error)` at `main` would write it to `e`, std's `io::Stderr` (§17, `io`): its full name, and each field of its payload by the writer `main`'s namespace sees for the field's type to an `io::Stderr`, the program's before std's, or without one by its derived text (§13, Formatting, rules 5 and 10). It is ctxlang code that the compiler writes around `main`, so a compiled program and `ctxc interp` write the same, and `main` needn't take an `Io` for it. A program that reports with more than that, or chooses its exit codes, returns an `i32`. Any other result type is an error, as is a `!` in a program whose std has no `io::Stderr` with a writer of text.
5. `#start` on a fn makes it the program's **start**, which runs `main`: the runtime calls it first, and the program's exit code is its result, an `i32`. Its context is capabilities without fields, which the runtime supplies as `main`'s, and any of these read-only fields: `argc: i32` and `argv: *?*u8`, C's; and `main: &fn{ args: Args } -> i32`, which calls `main` with its capabilities and `args`, and gives its exit code: for a `main` that returns a `!`, rule 4's, 1 after the error is written, so a start fn of a program's own gets the same report without doing anything for it, and one that never calls `main` gets none. std's (§17, `rt`) gives the runtime memory for function values' records (`pages_set`, beyond the little the runtime keeps itself) and the fn that writes a thread's standard output out when it ends (`ends_set`), sets up the platform, sets the stack limit (§15, rule 13), gives `main` its `args`, and writes standard output's buffer out once `main` returns. A start fn of a program's own that doesn't call `rt::pages_set` has only the runtime's own: past it, a bind or conversion that needs a record panics.
6. `#panic` on a fn makes it the program's **panic fn**: every panic calls it, `@panic` and the checks that panic alike. Its context is capabilities without fields, supplied as for `#start`, and any of these read-only fields: `msg: []u8`, the message; `file: []u8`, `line: u32` and `col: u32`, the panic's position, with a line of 0 for a panic without one, whose file is the program's path. It returns nothing, and it shouldn't return at all: the program stops at once if it does, or if it panics. Its own frames aren't checked for stack overflow, so it can report one. A panic on any thread calls it once for the program: a panic on another thread meanwhile waits for the program to end, and one on the thread that reports traps. std's (§17, `rt`) writes standard output's buffer out, then `FILE:LINE:COL: panic: MSG` (or `PROGRAM: panic: MSG`) to standard error, with `panic in task NAME:` for a panic in a task that runs on a worker, NAME being its task fn's (a task run at once is part of its starter), then the panic's call path, a line for each function (Call paths, below), and exits with 134. A panic fn of a program's own reads the path, or writes it as std's does, with std's `rt` (Call paths, rule 9).
7. Each is a fn with a body and no generic parameters, and neither may take a `Build` (§19). std declares one of each. A program's own replaces std's, so a program for a target without an OS can supply both; one with neither has no start, and a panic stops it at once. Two in the program, or two in std, are an error.
8. A program is **threaded** if `main` or its start fn takes `Threads` or a capability that includes it, or it has a callback that C may call from any thread (§18, Callbacks, rule 6): only such a program can run ctxlang code on more than one thread. Its runtime keeps the stack limit and the records of function values for each thread, behind a lock where threads share them, and its `#thread_local` statics are per thread (§15, rule 13). Any other program pays nothing for threads: the stack limit and those statics are plain globals, nothing is locked, and no thread library is linked. Which it is depends on the source alone.

### Call paths

```text
lib/script/nwarg.ctx:41:17: panic: index 5 out of bounds for length 3
  at nwarg::param (lib/script/nwarg.ctx:41:17)
  at routines::get_tag (lib/engine/routines/core.ctx:210:9)
  at scripts::run_program (lib/engine/scripts.ctx:88:5)
  at main (main.ctx:30:5)
```

1. A panic's **call path** is the calls in progress on its thread when it happened: the function the panic is in, then the function that called it, and so on. std's panic fn (Entry point, rule 6) writes it to standard error under the panic's line, which is as it was, a line for each function, innermost first: two spaces, `at NAME (FILE:LINE:COL)`. `ctxc interp` writes the same lines.
2. NAME is the function's name with its namespaces, and for a generic fn's instance its arguments: `list::push(i32, arena::Arena)`. FILE is the file that declares it, as a compile error names it (§21, rule 2). The first line's position is the panic's own; every other line's is that of the call the function made, at the `{` of its context, where an error about the call is. So each line but the first reads: this function, at this place, called the one above.
3. **What is in a path.** Every function of the program and of std that a call went through, a recursive one as often as it is in progress. Code the compiler wrote isn't: the code of a bound function or a function value, a conversion between function types (§5), a derived `==`, `@hash` or text (§13), an `@fmt`'s own function. A call through one of these is a line for the function that made it and a line for the function it reached: `apply(i64)`, then the `pick` its `f` was bound to. A path ends at `main`, at a test's fn (§20) or at a task's fn (rule 6): what called those is the runtime's.
4. **A long path** is written as its first 16 lines and its last 8, with a line between them that counts the rest: `  ... 10898 more frames`. A recursion that overflowed the stack is such a path.
5. **Where less is known,** the line says so, and never guesses:
   - `  at NAME (FILE)`, without a position: the function is known and where in it is not. That is a call the compiler wrote into it, as the end of a task handle's scope (§15, Tasks, rule 6), and a call past line 1048575 or column 4095 of its file, which a frame doesn't hold.
   - `  at C code (no position)`: C called a callback here (§18, Callbacks). The line above it is the callback, and the line below it the function that called into C, as a library that sorts with the program's comparison; on a thread the program didn't start, it is the path's last line.
   - **A panic without a position** (`PROGRAM: panic: MSG`) has a path all the same. For std's own (`rt::fail`) and for a native's, its first line is the function that called it, at that call. For a stack overflow it is the function that made the call that didn't fit, at that call: the function called isn't in the path. Reporting it takes no stack below the limit: the path is read from the frames as they are (rule 8), and the panic fn's own frames aren't checked (Entry point, rule 6).
   - A panic of the runtime's own, for memory for function values (Entry point, rule 5) or an `@record_copy` into too few bytes (Tasks, rule 5), has no path: only its line.
6. **Threads and tasks.** Each thread has its own path. A task that runs on a worker (§17, `task`) has a path that starts in its task fn and ends with where it was started, `  started at NAME (FILE:LINE:COL)`: the function that called the start, and the start's position. What that function's own callers were isn't kept: the starter has gone on. A task run at once is called by its start, so its path goes on through `task::start` into its starter.
7. **Which builds keep their paths.** `ctxc run` and `ctxc exe` of an executable at optimization level 0 or 1, which is every program without a build program and every executable whose build program doesn't call `build::optimize` (§19, rule 6); and `ctxc test` of any executable, at any level, since a test's failures say which calls led to them (§13, Checks, rule 9). An executable at level 2 or 3 keeps none: it asked for speed, and the paths cost a few percent (rule 8). `build::trace_calls{ &b, exe, on }` says otherwise, either way, for `run`, `exe` and `test` alike: `on = true` for an optimized executable whose panics should say how they were reached, as a tool that tests an engine, and `on = false` for one that gives them up. Without its paths, a panic's path is its first line alone, the function the panic is in: that costs nothing while the program runs, and is in every build. A program's behaviour is the same either way but for those lines.
8. **What it costs** (internals.md, How ctxlang maps to C): every function takes its caller's frame as a hidden first parameter, a function that calls has a frame of three words, and each call stores its position in it, one store. Nothing is kept in memory that outlives a call and nothing is undone on return, so a function the C compiler inlines with all it calls pays nothing. Measured on Windows with gcc: 4% on ctxc checking itself, 4% on a game's script VM at `-O2`, whose instructions take about twenty cycles each, 8% on a video decoder at `-O2`; an executable is 9% to 33% larger, its functions' names and the stores.
9. **For a panic fn, and anywhere else.** std's `rt` (§17) gives the path as values: `rt::count_frames{ &stack }` is how many entries it has and `rt::get_frame{ &stack, index }` entry `index`, innermost first, an `rt::Frame`: `name`, `file` (empty if it has none), `line` and `col` (0 where the position isn't known) and `kind`, an `rt::FrameKind`: `call`, `c_code` or `start` (rule 6). Both take a `mut stack: rt::Stack`, which a panic fn may take as any capability. While a panic is reported they give the panic's path; at any other time the caller's own, whose entry 0 is the function that asks, at that call. `rt::write_path{ &io, &stack }` writes a panic's path as rule 1 has it, for a `#panic` fn of a program's own; one that calls none of these writes no path. They are functions, not builtins: the runtime keeps the frames, and reading them needs nothing only the compiler knows (§13, rule 6).
10. **Under `--json`** (§21, rule 11) a panic's lines are the program's own text on standard error, as without it: `ctxc run` doesn't read what the program writes. The lines have this one shape so that a reader takes them apart: a line that starts with two spaces and `at `, `started at ` or `... ` after a panic's line is of its path. A test's panic is given as values in its record (§20, rule 15).

## 16. Open questions

Settled questions are removed, and the rest keep their numbers.

- **1. Dangling pointers across calls:** direct calls have inferred success/error and pointer-store origins (§14); indirect calls remain conservative, and origins through mutable arguments remain outside the check.
- **3. Allocator instance mismatch:** `alloc::resize`, `new` and `free` take the allocator's state on each call, and passing a different `S` instance of the same type than the memory came from isn't caught. Brands would close this. Lists, maps and builders keep a pointer to their state, so they can't mix instances.
- **4. Method sugar:** should `x.f{...}` mean `f{ first = &x, ... }`?
- **5. File = namespace:** should each file implicitly be a namespace?
- **6. Imports:** some form of `use list::List` to shorten long paths?
- **7. Variant shorthand:** should `.variant{...}` be allowed when the expected type is known?
- **9. Large stack frames:** should the compiler error or warn above a size limit? (Page allocation is now the `Mem` capability, §15.) Should pages be freeable?

## 17. Standard library

1. The standard library is ctxlang source (`std/*.ctx`) and one platform layer: `std/os/windows`, or for Linux and macOS `std/os/posix`, which they share, with `std/os/linux` or `std/os/macos` beside it. It is part of every program, with the layer of the platform it is built for, and a build program's has std/build/ too, with ctxc's lexer and parser (§19, rule 16). `ctxc interp` builds a program with the interpreter's layer, `std/os/interp`, instead, and the `target.ctx` of the platform it runs on; there, a `#start` fn's `argv` (§15, Entry point) is UTF-8 on every platform, where Windows' C gives the ANSI code page's bytes. Its extern fns (§18) are the operating system's and the C library's, except for a few that the runtime provides in C: panics without a position, memory for function values' records, and a thread's name, stack limit and end (`rt`), and floats as text and back (`ascii`), which a program links only if it uses them. Its state for the whole program is statics (§15, rule 13).
2. Its namespaces are visible from user code as if declared at top level. A user declaration with the same name shadows a std one (§10).
3. It allocates only through an allocator the caller passes in (§14), and does IO only through an `Io` or `Fs` the caller passes in (§15). Only `mem::pages` takes memory from the system, through a `Mem` the caller passes in.
4. A platform layer declares namespace `os`: what the rest of std needs from the operating system, over extern fns to the OS's own C functions and, through its capability `os::Proc`, C variables (§15, rule 12). Every layer declares the same functions and an `os::Proc`, so std's other files are the same on every platform, and each function that can fail declares the same set (§8, Errors, rule 14), `fs::Error` or `proc::Error`, whichever of it its OS gives, so a program checks the same on every platform. Linux's and macOS's share `os` and differ in namespace `sys`: the C library's numbers and layouts, and the functions it names differently. What the platform is, apart from how it is reached, is namespace `target`, in each platform's `target.ctx`: `OS`, `ENV_CASE` and `is_absolute`. The interpreter's layer, `std/os/interp`, is over extern fns that only `ctxc interp` provides (`ctx_interp_*`); what it can't do (standard input, files, other programs) stops the run.

| Namespace | Contents |
|---|---|
| `slice` | Helpers for built-in slices (§12): `empty`, `cast`, `copy`, `fill`, `eq_bytes` |
| `c` | What calling C needs (§18): the attribute `symbol { name: []u8 }`; `String { ptr: *u8 }`, C's NUL-terminated `const char *`, which a literal can be (`from_literal`, §18, which fails with `has_nul{ at }`), with `len` (the bytes before the NUL), `bytes` (a view of them) and `copy` (bytes and a NUL from an allocator; fails with `c::has_nul{ at }` or `alloc::out_of_memory`). |
| `Args` | Declared at the top level: `type Args = [][]u8`, the type of `main`'s `args` (§15). |
| `Io`, `Fs`, `Mem`, `Proc`, `Threads`, `Build`, `Test` | Declared at the top level: `capability Io` and so on (§15), in `io.ctx`, `fs.ctx`, `mem.ctx`, `proc.ctx`, `thread.ctx`, `build.ctx` and `test.ctx`. `Test` includes `Io`, `test::State` (§20) and `rt::Stack`, for the calls that led to a check (§13, Checks, rule 9). `Proc` includes `Io`, since the programs it starts share the console, and `Build` includes `Io`, where a build's graph goes without `CTX_BUILD_OUT` (§19), and is `#thread_bound`. `Io`, `Fs` and `Threads` include `task::Cancel`, and `Threads` includes `os::Threads`, `Mem` (the task backend keeps its table in pages) and `task::State` (§17, `task`). Each includes its namespace's `State` too (`io::State`, `proc::State`, `build::State`): std's state for the whole program, as statics (§15, rule 13). |
| `rt` | What starts a program and reports its panics (§15, Entry point): `start`, std's `#start` fn, and `report`, its `#panic` fn. `Stack`, a capability whose `#stack_limit` static `limit` is the stack limit (§15, rule 13), which `start` sets. `c_args` gives a layer the command line's arguments from C's `argv`. `pages_set` gives the runtime `record_pages` or another fn for memory for function values' records, and `ends_set` gives it `thread_ends`, which writes a thread's standard output out when the thread ends. `thread_begin` sets a new thread's stack limit and name, and `thread_name` is the calling thread's, empty on the main thread. `thread_runs` tells it the task a worker runs, for a path's last line. `fail` panics without a position, with a message that needn't be a literal; `Message`, `message`, `add`, `add_u64` and `fail_with` build one. Call paths (§15, Call paths): `Frame` (`name`, `file`, `line`, `col`, `kind`) and `FrameKind` (`call`, `c_code`, `start`), `count_frames` and `get_frame`, which take `mut stack: Stack`, `write_path` (a panic's path to standard error, as `report` writes it), and `write_frames` (the path from an entry on, with the words that start its lines: what `write_path` and `test::write_callers` are). |
| `thread` | What a thread does to itself: `sleep` (at least `nanoseconds`; in a task asked to stop, until then: it waits on the task's cancel object) and `yield_now`; `current_id`, a number unique to the calling thread while it runs. Each takes `mut threads: Threads`. What runs concurrently is a task (`task`). |
| `task` | Tasks (§15, Tasks; internals.md, Tasks), with the Threaded backend: each running task has a worker, a thread of the operating system, and a blocking call blocks it. `Task(R)`, a task's handle, which holds its result once it has ended, and `Group`, tasks that end together, both `#task_handle`; the errors `cancelled` (what a blocking call fails with in a task asked to stop) and `out_of_resources`; `start(R)` (maybe concurrently, maybe at once, on the caller's thread: no error; at once past the limit, without a thread or room in the table, and in the interpreter), `start_concurrent(R)` and `start_blocking(R)` (concurrently, or `out_of_resources`; the interpreter stops at them), and `start_in`, `start_concurrent_in` and `start_blocking_in` for a group, all `#starts_task`; `wait(R)` (the task's result; the handle is zero again), `wait_for(R)` (whether it ended within `nanoseconds`), `cancel(R)` (asks it to stop, waits, gives its result), `end(R)` (what a handle's scope ends with: `cancel` unless it is zero, the result dropped), `wait_all` (the first error of the group's tasks, which cancels the rest) and `cancel_all` for a group; `check_cancelled`; `set_limit` (busy workers past which `start` runs a task at once, 64 by default) and `set_stack` (workers' stacks, 8 MiB by default). Each takes `mut threads: Threads`. A worker waits 10 seconds for its next task, then ends. Cancelling a task asks it to stop: its blocking calls fail with `cancelled` (`io::read` returns 0, `thread::sleep` returns early), those that wait for long wait on its cancel object too (child pipes, child waits, standard input, sleep), and `fs`'s are checked before they block; a task that waits for another and is asked to stop cancels it. For std's blocking calls: `Cancel`, a capability whose `#thread_local` static is the calling task (`Io`, `Fs` and `Threads` include it), with `check`, `get_cancel_object`, `begin_synchronous` and `end_synchronous` (around a call only Windows' CancelSynchronousIo interrupts). `State`, the backend's table, which `Threads` includes; `begin`, a worker's first fn, for the platform's layer. |
| `atomic` | `Order` (`relaxed`, `acquire`, `release`, `acquire_release`, `sequentially_consistent`), the order of an atomic (§13, Atomics). |
| `mutex` | `Mutex`, a lock one thread at a time holds, not recursive: Windows' slim reader/writer lock, or a `pthread_mutex_t`. `make`, `lock`, `try_lock` (without waiting: whether it locked), `unlock`, `free`. Each takes `mut mutex: Mutex` but `make`, and no capability: they only wait. |
| `condition` | `Condition`, which threads wait on with a mutex: Windows' condition variable, or a `pthread_cond_t`. `make`, `wait` (unlocks the mutex, waits for a signal and locks it again, and may wake without one), `wait_for` (as `wait`, giving up after `nanoseconds`: false if it did; it reads the clock, so it takes `mut threads: Threads`), `signal` (one waiting thread), `broadcast` (all of them), `free`. |
| `proc` | `Proc` includes the layer's `os::Proc` (rule 4) and `Io`. The errors `not_found`, `permission_denied`, `broken_pipe` (a `write` to a child's input after the child closed it) and `other{ code }`; `run` (starts a program found on PATH, with extra `KEY=VALUE` environment entries, sharing standard input, output and error, and returns its exit code, a `!i32`: 128 + N if signal N killed it), `spawn` (starts one without waiting for it, with `Options`, and returns a `!Child`), `wait` (waits for a `Child`, once, returns its exit code as `run` does, ends what is left of its group with `leftovers = kill`, and releases it: its handle, its Job Object, and its pipes still open, which it closes and sets to null), `wait_for` (as `wait`, giving up after `nanoseconds`, a `!?i32` that is null while the child runs; 0 looks without waiting, and a wait that gives up releases and ends nothing), `kill` (ends a child at once, with its group if it has one; its exit code is then 128 + 9 on every platform, and it must still be waited for), `read` (some of what a child writes to a pipe; 0 at its end), `write` (all of the bytes into a child's input) and `close` (a `?Pipe`, which it sets to null), `processors` (how many processors the program may run on), `env` (an environment variable, or null), `environment` (the environment's `KEY=VALUE` entries), `exe_path` (this program's executable), `os` (the operating system, a `build::Os`). `Options` has defaults (§7, rule 4): `env` (extra entries, `[]`), `dir` (the working directory, `""` for this program's), `stdin`, `stdout` and `stderr`, each a `Stdio` (`inherit`, this program's own stream, the default; `ignore`, the null device; `pipe`, one this program holds the other end of; `file{ file }`, an open `fs::File`, of which the child gets its own copy), `group` (`false`; a process group on Linux and macOS, a Job Object on Windows, which `kill` ends whole), `leftovers` (a `Leftovers`, for a group: `kill`, the default, which `wait` ends what is left of the group with once the child has ended, killing the process group before the child is reaped so that its id can't be another group's, or closing a Job Object that ends what is in it; or `keep`, which leaves it running) and `die_with_parent` (`false`; the child ends when this program does: on Linux when the thread that started it does, `PR_SET_PDEATHSIG`, and on Windows through a Job Object that ends it when it is closed; once the child has ended, what it started is let go of unless `wait` ends it with `leftovers = kill`, on Windows by clearing the job's `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` before closing it; macOS has no such thing, and ignores it). A `Child` has `id` (a process id, or a process handle on Windows), `group` (the group's id or Job Object's handle, 0 without one), `cleanup` (what `wait` does once the child has ended, for the platform's layer: the process group it kills, or on Windows the Job Object whose leftovers it lets go of; 0 for nothing) and `stdin`, `stdout` and `stderr`, each a `?Pipe` (`id`, a file descriptor or a HANDLE). Starting a program on Linux forks, so that the child can ask to end with its parent; macOS starts one with `posix_spawnp`. No function starts a thread. Every function takes `mut proc: Proc`. |
| `build` | Build programs (§19): `Exe`, `Os` (`windows`, `macos`, `linux`); `exe`, `add_sources`, `gen_file`, `optimize`, `trace_calls`, `link`, `framework`, `lib_path`, `deny_unchecked`, `os`; the attribute `sources { dir: []u8 }`, for the build program's own files. Every function takes `mut b: Build`. In a build program only, from std/build/ (§19, rule 16): `declarations` (§19, rules 14 and 15), which takes `mut fs: Fs`, `mut mem: Mem` and an allocator too, and returns a `!Declarations`: `decls`, `diags` and `files`. A `Decl` has `kind` (a `Kind`: `structure`, `tagged_union`, `extern_union`, `enumeration`, `function`, `extern_function`, `constant`, `alias`, `capability_type`, `error`), `name`, `path`, `generics`, `attrs`, `fields`, `variants`, `ty` (a const's type, what a `type` names, an enum's base), `value` (a const's), `result` (a fn's), `file`, `line` and `col`. A `Field` has `name`, `ty`, `mutable`, `attrs` and `value` (a struct field's default, §7, rule 4; empty without one); a `Variant` `name`, `fields`, `payload` (it has braces) and `value` (an enum's `= e`); an `Attr` `name` and `fields`, `AttrField`s, each with `name`, `value` (its text) and `literal` (a `Literal`: `string{ bytes }`, `integer{ negative, value }`, `boolean{ value }` or `other`); a `Diagnostic` `file`, `line`, `col` and `message`. |
| `fs` | `File`, `Mode` (`read`, `write`, `append`, `create`); the errors `not_found`, `permission_denied`, `is_directory`, `exists`, `not_directory`, `not_empty`, `bad_file` and `other{ code }` (the OS's number); `open`, `read`, `write`, `seek` (to an offset from the start), `read_at` (fills a buffer from an offset, short only at the end of the file, without the file's position: `pread`, or `ReadFile` at an offset on Windows, so tasks may read one open file at once; the position is unspecified after it), `close`, `size`, `remove`, `make_dir`, `remove_dir` (an empty directory; it fails with `not_empty` otherwise, so removing a tree is the caller's: its entries first), `rename` (replacing any file at the new path), and `read_all` (into memory from an allocator), `write_all`, `list` (a directory's entry names, sorted, in one allocation, which `list_free` frees) and `make_absolute` (a path joined to the working directory unless it is absolute, into memory from an allocator); `is_absolute`. Every function but `is_absolute` takes `mut fs: Fs` and returns a `!T`, or a bare `!` (`close`, `remove`, `make_dir`, `remove_dir`, `rename`), that fails with the errors its body can produce (§8, Errors), and `read_all`, `list` and `make_absolute` with `alloc::out_of_memory`. A `File`'s `id` is the OS's handle: a file descriptor, or a Windows HANDLE. The platform layer does the work (`os`, below). |
| `alloc` | `Bytes` (`[]mut u8`), the allocator type `Fn(S)`, the error `out_of_memory`, typed `resize(T, S)`, `make(T, S)` for `count` new `T`s, each its zero value, and `new(T, S)` and `free(T, S)` for one `T`: `new` returns a `!*mut T` holding the given `value`. `resize`, `make` and `new` fail with `out_of_memory`; resizing to 0 frees and doesn't fail. |
| `mem` | `PAGE` (4096); `pages`: at least `size` bytes of zeroed, page-aligned memory (`size` rounded up to a multiple of `PAGE`), as a `?alloc::Bytes`, valid until the program ends, or null; `reserve`: the same for an arena's buffer, made usable as the arena reaches it, so a generous size costs address space rather than memory (on Windows, where `pages` commits all of it), and only an arena may use it. Both take `mut mem: Mem`. |
| `os` | The platform layer (rule 4): `OS`, the `build::Os` it is for; `write` (some of the bytes, which aren't empty, to an `io::Stream`; how many, 0 after an error), `read` (some of standard input; 0 at the end or after an error), `pages` (zeroed, page-aligned memory of a size that is a multiple of `mem::PAGE`, or null), `reserve` (the same for an arena, reserved) and `commit` (makes an arena's memory usable as it reaches it), `env` (an environment variable, or null), `environment` (the environment's `KEY=VALUE` entries); for `rt`, `start` (what the platform needs before `main` runs), `args` (the command line's arguments) and `exit`; for `proc`, `spawn` (a `proc::Child`), `wait`, `wait_for` and `kill` (of a `proc::Child`), `pipe_read`, `pipe_write` and `pipe_close` (of a pipe's `id`), which fail with `proc`'s errors, `processors`, `exe_path` and `ENV_CASE` (whether the environment's keys are case-sensitive); and for `fs`, over paths that aren't empty: `file_open`, `file_read`, `file_write` (some of the bytes), `file_seek`, `file_close`, `file_size`, `remove`, `make_dir`, `remove_dir`, `rename`, and `Dir` with `dir_open`, `dir_next` (the next entry's name, or null) and `dir_close`, which fail with `fs`'s errors; `working_dir` (the working directory's path, into a buffer) and `is_absolute`; for `task` and `thread`, `Threads`, a capability without fields that std's `Threads` includes, `CONCURRENT` (whether tasks may run concurrently: not in the interpreter, whose `concurrency_unsupported` stops the run), `thread_create` (a thread that runs `task::begin` with a stack of a size, or null), `thread_detach`, `thread_sleep`, `thread_yield`, `thread_id`, `thread_name` (the calling thread's, for debuggers), `thread_handle` and `cancel_synchronous` (Windows' CancelSynchronousIo; nothing elsewhere), `now` (a monotonic clock), a task's cancel object with `event_make`, `event_signal`, `event_reset`, `event_waitable` (what a wait waits on: an event's handle, an eventfd, a pipe's read end) and `event_wait` (sleep in a task), and `Mutex` and `Condition` with `mutex_make` and the rest, for `mutex` and `condition`; `wait`, `wait_for`, `pipe_read` and `pipe_write` take `mut cancel: task::Cancel` too, and wait on its object in a task (this program's ends of child pipes don't block on Linux and macOS, so they are polled), and `read` waits on it for standard input. The interpreter's stops the run where one thread would wait for another: for a mutex another holds, or on a condition. `Proc`, a capability without fields that std's `Proc` includes: on posix it names C's `environ` (§15, rule 12), on Windows a static (§15, rule 13), the counter that names its pipes. `write` and `read` take `mut io: Io`; `pages`, `reserve` and `args` (with `argc: i32` and `argv: *?*u8`) `mut mem: Mem`; `commit` (`first` and `last`, `*u8`s), `is_absolute`, `thread_id`, `thread_name` and the mutexes' and conditions' nothing; the other threads' `mut threads: Threads`; `start` `mut io: Io`, `mut proc: Proc` and `argv`; `env`, `exit`, `spawn`, `wait`, `wait_for`, `kill`, `pipe_read`, `pipe_write`, `pipe_close`, `processors` and `exe_path` `mut proc: Proc`, the layer's own; the rest `mut fs: Fs`. `io`, `mem`, `proc` and `fs` call them, so they are the same on every platform. |
| `arena` | `Arena`, a bump allocator: `new`, `alloc` (an `alloc::Fn(Arena)`, which makes memory from `mem::reserve` usable as it reaches it), `reset`, `mark` and `restore` (frees what was allocated after the mark), `remaining`. It hands out its buffer's bytes as they are the first time, and zeroes them when it hands them out again |
| `list` | `List(T, S)`: `new`, `reserve`, `push`, `pop`, `get`, `set`, `at`, `items`, `take` (the items in an allocation of their number, which frees as one), `clear`, `each`, `free`. `new` takes the allocator's function and a pointer to its state, and the list keeps both, so it must not outlive the state (§14). `reserve` and `push` return a bare `!`, and `take` a `![]mut T`, that fails with `alloc::out_of_memory`, leaving the list as it was. |
| `map` | `Map(K, V, S)`, a hash map that holds its allocator as a list does, and its key type's hash and equality functions: `make`, which gives it `K`'s own `@hash` and `==` (§13, Hashing), so that a struct, a union, a string or any other type that has them is a key with nothing written for it, and a `K` without them is an error at the call; `new`, which takes a `hash` and an `eq` of the caller's instead; `hash_key` and `eq_keys`, `@hash` and `==` as functions of a key type; `len`, `has`, `get`, `at`, `put`, `remove`, `clear`, `free`, `next`, `each`. `put` returns a bare `!` that fails with `alloc::out_of_memory`, leaving the map as it was. `hash_*` and `eq_*` for `i32`, `i64`, `u32`, `u64`, `usize`; `hash_bytes` for byte slices, with `slice::eq_bytes`; `hash_string` for `utf8::String`, with `utf8::eq`. |
| `ascii` | Byte-level character tests and case for a `u8`: `is_digit`, `is_upper`, `is_lower`, `is_alpha`, `is_alnum`, `is_space`, `to_upper`, `to_lower`. Extern fns, used by `utf8`'s and `fmt`'s numbers, which the runtime provides in C (`ctxc/rt/ctxfloat.c`): `f64_digits`, `f32_digits` (a float's text, §13, Formatting, rule 9), `f64_fixed` (with a precision), `f64_parse`, `f32_parse`. |
| `fmt` | What an `@fmt` hole with a spec is written from (§13, Formatting, rule 8). `Spec`: `width` (0 without one), `precision` (-1 without one), `align` (an `Align`: `natural`, `left`, `right`, `center`), `zero`, `base` (10, 16, 2 or 8) and `upper`. The values a spec's hole gives its writer, each with its `spec`: `Int { n: i64 }`, `Uint { n: u64 }`, `F64 { x: f64 }`, `F32 { x: f32 }` and `Text { s: []u8 }`. For a writer of a program's own sink: `format_int`, `format_uint`, `format_f64` and `format_f32`, each the value's text as its spec says in a buffer of `LONGEST` bytes, and for a `Text` `pad_before` and `pad_after`, how many spaces go around it, with `spaces`, that many as static bytes; `count`, a string's characters. `WIDEST` (255) and `FINEST` (30) are the largest width and precision. |
| `utf8` | `String { bytes: []u8 }`, the text type: a non-owning view of valid UTF-8. Offsets are in bytes, and an offset inside a character panics; a character is a `u32` code point. `from` (checks the bytes, returning a `!String` that fails with `invalid{ at }`, the offset of the first bad byte), `from_literal` (a literal's conversion, §18: `from` while compiling), `of` (panics if invalid), `empty`, `len` (bytes), `count` (characters), `is_boundary`, `at`, `sub`, `eq`, `starts_with`, `ends_with`, `find`, `find_str`, `split_once`, `trim`, `trim_start`, `trim_end`, `encode`, `is_scalar`, `is_ascii`. Character tests and case (ASCII only). `parse_i64`, `parse_u64`, `parse_f64`, `parse_f32`, `fmt_i64`, `fmt_u64`, `fmt_f64`, `fmt_f32`. `Cursor`: a read position for lexers, by character: `cursor`, `done`, `rest`, `peek`, `peek_at`, `bump`, `eat`, `eat_str`, `take_while`, `skip_space`. `Builder(S)`: a growable string that owns its bytes and holds its allocator as a list does, with `push`, `push_char`, `push_i64`, `push_u64`, `push_f64`, `push_f32`, `push_bool`, `view`, `clear`, `free`. Its `@fmt` writers (§13, Formatting), marked `#write`, are `push` for a `String`, `push_literal` for a `strlit`, `push_bytes` for a `[]u8` (and so a `[]mut u8`: a byte that starts no valid UTF-8 sequence becomes U+FFFD), `push_bool`, `push_f32`, `push_f64`, and `push_` and the type for each integer type (`push_i8` ... `push_usize`); `push_char` isn't one; and for a hole with a spec, `push_fmt_int`, `push_fmt_uint`, `push_fmt_f64`, `push_fmt_f32` and `push_fmt_text`, whose text's bytes go in as `push_bytes` has them. For a hole written another way: `write_char`, and from before specs `write_hex`, and padded to a width with spaces, or zeros after any `-`: `push_padded` (a `String`), `push_int`, `push_uint`, `push_hex`. `push_json` writes bytes as a JSON string, in its quotes, whatever they are: `"`, `\` and the bytes below 32 escaped, and a byte that starts no valid UTF-8 sequence as `\ufffd`; it isn't a writer, and is named in a hole, `utf8::push_json{ s = path, _ }`. `Fmt(S)` is a writer into a `Builder(S)`, `&fn{ mut b: Builder(S) } -> !`. Each push and write returns a bare `!` that fails with `alloc::out_of_memory`. `fmt_hex` writes an unsigned integer in hexadecimal into a buffer. |
| `test` | What runs a program's tests (§20). `main`, std's `#test_main` fn: the runner, which starts each test in a process of its own, and in that process the test (§20, rules 6 to 10). `Case`, a test as the compiler lists it: `name` (the fn's, with its namespaces), `file`, `line`, `dir` (the file's directory, as an absolute path), `panics` (whether it is a `#test{ panics = "text" }`) and `message` (the text), `skips` (whether it is a `#test{ skip = "why" }`) and `why` (the text). `check{ &t, held, file, line, text }`, what an `@expect` calls (§13, Checks): it counts the check, and for one that didn't hold notes that the test failed, starts the failure's line on standard error, `FILE:LINE: fail: NAME: TEXT`, and returns `held`. `require{ &t, held, file, line, text }`, what a `@require` calls: `check`, with `required: ` before TEXT. `write_callers{ &t }`, what either calls after the line of a check that didn't hold: the calls that led to the check's function, a line each (§13, Checks, rule 9). `stop{ &t }`, what a `@require` that didn't hold calls once its line is written: it writes out standard output's buffer and ends the process with exit code 1, so it never returns; the compiler supplies its `Test` (§13, Checks, rule 8). `skip{ &t, why }` ends the running test as skipped (§20, rule 5): it writes `FILE:LINE: skip: NAME: WHY` to standard error and ends the process as `stop` does, with exit code `SKIPPED`, 77; after a check that didn't hold it writes nothing and the code is 1. `dir{ &t }` is the directory of the running test's own source file, as an absolute path (§20, rule 12). `args{ &t }` is the arguments the run gives its tests, a `[][]u8`: what follows `--` in `ctxc test`'s (§20, rule 13). For a `#test_main` fn, `pass_args{ &t, args }` hands the tests those of its own `args` that follow the first `--`, and `own_args{ args }` is those before it. `end{ &t, code }` is what both end the process with, through C's `exit`, which std declares for a `Test` here: all that a `Test` may end. In a process std's runner started for one test it first writes the test's report, `FILE:LINE: checks: NAME: N` (§20, rule 7). `checks{ &t }` is how many checks the running test has made so far, a `u64`: after `run_here`, those of the test it ran. `run_here{ &t, c, index, run }`, for a `#test_main` fn: runs test `index`, whose `Case` is `c`, in this process through the compiler's `run`, with its name set for its failures' lines, and gives 0 if it passed, or 1 if it returned an error, a check didn't hold or it made none, each written by then; a test that must panic and returned gives 0, since only its runner sees that no panic came; a `#test{ skip = "why" }` isn't run, and gives `SKIPPED` after its skip's line is written; a `@require` in the test that doesn't hold, or a `skip`, ends the process, and `run_here` doesn't return. `State`, a capability that `Test` includes: the running test's name, file, line and directory, the tests' arguments, how many checks it has made and whether one failed, as statics (§15, rule 13), set atomically, so a test's tasks may check through one `Test`. |
| `cmp` | The first or the last of two values by an order the program gives, for a type without one (§11, Expressions, rule 1): `min_by{ a, b, less }` and `max_by{ a, b, less }` take the order as a function, a `Less(T)`, which is `&fn{ a: T, b: T } -> bool`, whether `a` comes before `b`. They give the one that comes first, or last, by it, and `a` where neither comes before the other. Each argument is evaluated once, as a call's are. The smaller and the larger of two numbers and a number between two bounds are builtins: `@min`, `@max` and `@clamp` (§13, Smallest, largest and clamped). |
| `math` | The C library's math functions, with libm's names, `#pure` (§18): for `f64`, `sqrt`, `cbrt`, `hypot`, `pow`, `exp`, `exp2`, `log`, `log2`, `log10`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `sinh`, `cosh`, `tanh`, `floor`, `ceil`, `round` (halfway cases away from zero), `trunc`, `fabs`, `fmod`, `fmin`, `fmax`, `copysign`, and each with an `f` suffix for `f32` (`sqrtf`). They run while compiling too, the only extern fns that do (§14, rule 1), so a const may be `math::sin{ x = math::PI / 8.0 }` or a table a loop fills: ctxc, itself a program built with the C compiler it builds with, calls the same C function, and a program's call is never computed by its C compiler, so a const's call and the program's with the same arguments give the same bits, a NaN's sign and payload included. That holds where ctxc and the program use one C library, as they do on the machine that builds both; ctxc doesn't build for another machine. A program's own declaration of one of these functions, by C's name and with these types, runs while compiling as well. Between C libraries, `sqrt`, `floor`, `ceil`, `round`, `trunc`, `fabs`, `fmod`, `fmin`, `fmax` and `copysign` are exact and the same everywhere; the others may differ in the last bit. `PI`, `TAU`, `E`, `PI_F32`, `TAU_F32`; `INF` and `NAN`, and `INF_F32` and `NAN_F32`: the infinity (`-math::INF` is the negative one) and the quiet NaN with a clear sign and no payload, which no literal is (§11, Literals, rule 2); `is_nan`, `is_inf`, `is_finite` (an `f64`, which an `f32` widens to); `f32_from_bits`, `f32_to_bits`, `f64_from_bits`, `f64_to_bits`. |
| `io` | `Stream` (an enum: `out`, `err`); `print`, `println`, `eprint`, `eprintln` for `utf8::String`, `newline`, `put_char` (one character), `print_i64`, `print_u64`, `print_f64`, `print_f32`, `print_bool` and their `println_` forms (smaller number types widen to these), `read_line` (bytes that aren't valid UTF-8 become `?`), `write` and `read` (bytes), `flush`, `put` (bytes past the buffer, through `os::write`). `@fmt` writers onto an `Io`, to standard output (`_ = @fmt(&io, "{} files\n", n)`), and onto a `Stderr`, which `to_stderr` makes from one: `write_` and the type, and `ewrite_` and the type, for a `strlit` (`text`), `utf8::String` (`string`), `[]u8` (`bytes`, as they are), `c::String` (`cstring`), `bool`, `f32`, `f64` and each integer type, and for a hole with a spec `fmt_int`, `fmt_uint`, `fmt_f64`, `fmt_f32` and `fmt_text`. They don't fail. Standard output is buffered: it is written out before anything goes to standard error or is read from standard input, and when the program ends or panics. The buffer is io's static (§15, rule 13), since a panic flushes it too: `State`, a capability that `Io` includes, whose `out` is an `Out`, `#thread_local`: each thread has its own, written out when the thread ends, so what threads print interleaves by line, not by byte. |

```ctx
fn main { mut io: Io } {
    io::println{ &io, s = "hello" }                    // a utf8::String viewing static bytes (utf8::from_literal)
    io::println_i64{ &io, n = 42 }
}
```

## 18. C functions and attributes

<!-- context:
capability Glfw
fn main {} {}
-->
```ctx
#c::symbol{ name = "labs" }
#pure
extern fn long_abs { n: i64 } -> i64

#pure
extern fn frexp { x: f64, mut exp: i32 } -> f64
extern fn glfwPollEvents { mut glfw: Glfw }      // a capability says who may call it
```

### Attributes

1. `#path` or `#path{ field = e, ... }`, on its own line before a declaration or a declaration's field, is an **attribute** of it: a field of a struct, an extern union, a union variant's payload, an error, a capability or a fn's or extern fn's context. Any of them may have several. A field's attributes are for build programs (§19, rule 14): except for a capability's (§15, rules 12 and 13), they change nothing the program compiles to. A function type's fields (`fn{ ... } -> R`, §5) declare nothing and can't have attributes, nor can a union's or an enum's variants themselves.

<!-- context:
namespace ecs {
    struct key {}
    struct cascade { depth: u32 }
    struct by { name: []u8 }
}
fn main {} {}
-->
```ctx
struct Pos {
    #ecs::key
    #ecs::cascade{ depth = 2 }
    x: f32,
    y: f32,
}

fn movement {
    #ecs::by{ name = "pos" }
    mut pos: Pos,
    dt: f32,
} { pos.x = pos.x + dt }
```

2. `path` names a struct, and the braces are a literal of it, checked as a const's initializer is and folded (§14): it can't call a function or use a const that isn't folded. `#path` alone means `#path{}`. A field of a number type or `bool` may be left out, and is then 0 or `false`: `#c::callback` is `#c::callback{ any_thread = false }`. A field with a default (§7, rule 4) isn't: `..` takes it from its default, as in any literal.
3. Attributes are data. The compiler acts on those of std's `c` namespace (`c::symbol` on an extern fn or a C variable, `c::callback` on a fn) and ignores the rest; a build program reads them as written with `build::declarations` (§19, rule 14), and their checked values later (todo/metaprogramming.md). ctxc's driver reads std's `build::sources` on a build program's `fn build` before compiling it (§19, rule 12); to the checker it is data, as any other.
4. The compiler declares `convert` (Literal conversions, below), `write` (§13, Formatting), `start` and `panic` (§15, Entry point), `stack_limit` and `thread_local` (§15, rule 13), `task`, `thread_bound`, `starts_task` and `task_handle` (§15, Tasks), `test` and `test_main` (§20) and `pure` (Extern functions, rule 8) itself. Only `test` takes a field, `#test{ panics = "text" }`. A namespace is never an attribute, so `#task` is the compiler's beside std's namespace `task`. They have no namespace, and a declaration of the same name shadows one. These, `c::symbol` and `c::callback` are errors anywhere they mean nothing, a field that isn't a capability's included.

### Extern functions

1. `extern fn name { context } -> R` declares a function that C provides. It has no body and no generic parameters.
2. It calls the C symbol `name`, or the one `#c::symbol{ name = "..." }` gives. The symbol must be a C identifier.
3. Its context fields are C's parameters in the order they are declared. A field with a capability type (§15) isn't passed: it only says who may call the function. A `mut` field of type `T` is passed as a `T*`.
4. A field or result may have a numeric type, `bool`, an enum (as its base type), a pointer (as a C pointer), a `?*T` or `?*mut T` (as a C pointer, with `null` as `NULL`: §8, Optional, rule 6), a C function pointer `extern fn{C} -> R` or its `?` (§12), a `c::String` or `?c::String` (as a `const char *`, below), a slice (as a struct of `ptr` and `len`), a struct (as a C struct of the same layout) or an extern union (as a C union, §12). Other types are an error, other optionals included.
   A `c::String` is C's `const char *`: a struct around one pointer, which C takes and returns as the pointer, and a `?c::String` is one that may be `NULL` (§8, Optional, rule 6). A literal where one is expected points to its bytes, which the hidden zero ends (`c::from_literal`; §11, Literals). A `c::String` built from any other `*u8` (`c::String{ ptr = p }`) must point to bytes that end in a NUL; that isn't checked.
5. Every call goes through a declaration of the symbol made for that function, so it can't clash with the declaration of the same symbol in a C header. Nothing checks the declaration against C's: a wrong one is undefined behaviour.
6. An extern fn is called like any function and is a value of type `fn{C} -> R`; where an `extern fn{C} -> R` is expected, it is its C symbol's address instead (§12, C function pointers).
7. Every program is linked with the C library and the math library.

8. §1.3 holds by declaration: every extern fn has a capability field, for the IO, OS or memory outside its pointer arguments it reaches, or `#pure`, which says it has no effect beyond the memory its pointer arguments reach and its result depends only on its arguments and that memory, as `sqrt`'s. One with neither, or with both, is an error, as is `#pure` on any other declaration. The compiler can't check the C side.

9. C's global variables have no declaration of their own: a capability names them, `extern name: T` among its fields, and only its namespace reads them (§15, rule 12). Reading one is as much an effect as calling an extern fn that takes the capability.

### Literal conversions

```ctx
// std's utf8 has `#convert fn from_literal { s: strlit } -> !String`
namespace regex {                                // a program's own type
    struct Regex { source: []u8 }
    error empty

    fn compile { bytes: []u8 } -> !Regex {
        if bytes.len == 0 { return empty }
        return Regex{ source = bytes }
    }

    #convert
    fn from_literal { s: strlit } -> !Regex { return compile{ s.bytes } }
}

fn main { mut io: Io } {
    io::println{ &io, s = "hello" }              // utf8::from_literal, run while compiling
    let r: regex::Regex = "[a-z]+"               // a bad pattern is a compile error
}
```

1. `#convert` on a fn makes it a **literal conversion**: a string literal where the type `T` of its result is expected is the fn's result for the literal (§11, Literals). Any namespace may declare one, for any `T`, so a library can give literals to a type it doesn't own.
2. The fn has a body and no generic parameters. Its context is one read-only field of a literal type, `s: strlit`, so it takes no capability and can run while compiling. Its result is a `T` or a `!T`, where `T` isn't a `strlit`, a `[]u8` or a `[N]u8`, or a `?` of one, which a literal is without one.
3. "Expected" is where widening applies (§11, Widening, rule 1), a const's initializer, an `if` or `match` branch next to one of type `T` (§11, Literals), and a call's `strlit` field, so `utf8::from_literal{ s = "hi" }` calls one directly, as any fn. Where a `?T` is expected, a conversion to `?T` comes before one to `T`. Only literals convert: no other value does, and conversions don't chain.
4. A literal sees only the conversions its code could name (§10, Name lookup): those in its namespace or one around it, or in a named namespace inside one of those, as `a::b::` names it. The program's top level has no name, so std's code sees only std's conversions, and the program's sees std's and its own. Two conversions to one `T` that a literal sees are an error at it, naming both, and not before: two libraries may each declare one, and a program may call either.
5. The conversion runs once the bodies are checked, as a const's initializer does (§14), and the program holds its result. The same limits apply, and the result may hold no pointer but one into the literal's bytes. An error result is a compile error at the literal, printed as `@fmt` writes an error (§13), with each field a number or a `bool`, or `_` for any other type: `string literal: utf8::invalid{ at = 3 }`. A const whose initializer holds a converted literal is run, not folded, and an attribute can't hold one.

### Callbacks

<!-- context:
capability Glfw
struct Window { id: u32 }
fn main {} {}
-->
```ctx
type KeyFn = extern fn{ mut glfw: Glfw, window: *mut Window, key: i32, scancode: i32, action: i32, mods: i32 }
extern fn glfwSetKeyCallback { mut glfw: Glfw, window: *mut Window, cb: ?KeyFn } -> ?KeyFn

#c::callback
fn on_key { window: *mut Window, key: i32, action: i32 } {}

fn listen { mut glfw: Glfw, window: *mut Window } {
    _ = glfwSetKeyCallback{ &glfw, window, cb = on_key }
}
```

1. `#c::callback` on a fn lets C call it. The fn has a body and no generic parameters, and its fields and result follow an extern fn's rules (rule 4 above).
2. Where an extern fn type `extern fn{Cs} -> Rs` is expected (or its `?`), the callback's name is a C function of that type, which calls it. The callback must be accepted where `fn{Cs} -> Rs` is (§5), but with no field read through a pointer: each of its fields is one of `Cs`, with the same type and the same mutability, since a `mut` field's pointer is C's, and its result is `Rs`. Fields of `Cs` it doesn't take are dropped, and the order of its own fields doesn't matter.
3. Only the name converts. A function value, a bind or a callback stored in a local doesn't (§12, C function pointers, rule 5).
4. C doesn't pass capability fields (rule 3 above), so the callback receives them without C passing them. Declaring a capability in a callback type is the binding's promise that C calls it only while that capability is held: for GLFW, within the call that polls events. The compiler can't check it. A capability with fields (§15, rule 5) can't be one of them, in the callback's fields or in the type its name converts to: nothing could supply it.
5. State reaches a callback through C: a pointer the library hands back (a `void *` user pointer, typed as the binding chooses), or a `mut` field, which is C's pointer.
6. C must call a callback on the thread that called into C, unless it has `#c::callback{ any_thread = true }`: then C may call it from any thread, such as a library's own (SDL's audio callback), which holds no capability, so the callback takes none. On a thread the program didn't start, it runs with the stack check off (§15, rule 13), since that thread's stack is unknown, and with the runtime's state for the thread until it returns. Calling any other callback from another thread is undefined behaviour. A program with one is threaded (§15, Entry point, rule 8).
7. A callback is still a fn: ctxlang code may call it, and use it as a `fn` value.

## 19. Build programs

<!-- context:
// file: tools/viewer/build.ctx
...
// file: tools/viewer/main.ctx
fn main {} { _ = format::Format::png }
// file: lib/derive/derive.ctx
namespace derive {
    fn enum_source { mut heap: arena::Arena, name: []u8, variants: [][]u8 } -> []u8 {
        let mut b = utf8::builder{ realloc = arena::alloc, &heap }
        _ = @fmt(&b, "namespace format {{ enum {}: u8 {{", name)
        for v in variants { _ = @fmt(&b, " {},", v) }
        _ = @fmt(&b, " }} }}")
        return utf8::view{ b }.bytes
    }
}
// file: lib/formats/formats.ctx
namespace formats { fn count {} -> u32 { return 3 } }
// file: lib/platform/platform.ctx
namespace platform { fn word { p: *u8 } -> *u32 { return @cast(*u32, p) } }
-->
```ctx
// tools/viewer/build.ctx: a tool, made of its own directory and of libraries other programs share
#build::sources{ dir = "../../lib/derive" }            // a generator, which the build program uses
fn build { mut b: Build } {
    let exe = build::exe{ &b, name = "viewer", root = "." }
    build::add_sources{ &b, exe, dir = "../../lib/formats" }
    build::add_sources{ &b, exe, dir = "../../lib/platform" }
    build::deny_unchecked{ &b, exe, except = ["../../lib/platform"] }   // only the binding may write `@cast` and the like
    build::optimize{ &b, exe, level = 2 }
    build::link{ &b, exe, lib = "SDL2" }
    match build::os{ &b } {
        macos   => { build::lib_path{ &b, exe, path = "/opt/homebrew/lib" } }
        windows => { build::link{ &b, exe, lib = "gdi32" } }
        linux   => {}
    }
    let mut buf: [65536]u8
    let mut heap = arena::new{ buf = buf[..] }
    let names: [3][]u8 = ["png", "tga", "dds"]
    // format.ctx, one of the viewer's files: `enum Format: u8 { png, tga, dds }` and its names
    build::gen_file{ &b, exe, name = "format", text = derive::enum_source{ &heap, name = "Format", variants = names[..] } }
}
```

1. A program that is a directory may have a `build.ctx` at its top: its **build program**, compiled and run before anything else is built. It describes the executables to build, which files each is made of, and how each is compiled and linked. Platform choices are ordinary code.
2. A build program is a program whose entry point is `fn build` instead of `fn main`: §15's rules for `main` apply to it. So `build` may return `!` or `!i32` (§15, Entry point, rule 4), and pass up with `try` what reading a directory or checking a source fails with: the error is written to standard error as `main`'s is, the build program exits with 1, and nothing is built. A program with a `main` has no other entry point, and a `fn build` in it is an ordinary function.
3. Only `build` may take a `Build` (§15): `main` can't, nor a `#start` or `#panic` fn. A `Build` includes an `Io` (§17).
4. `build::exe{ &b, name, root }` names an executable built from the `.ctx` files of directory `root`, not of its subdirectories, which may have none if the executable has generated files (rule 13), and returns a `build::Exe` for the calls that add to it. Two executables of one build can't have the same name, nor on Windows names that differ only in case. `build::os` is the operating system the build is for.
5. `build::add_sources{ &b, exe, dir }` adds the `.ctx` files under directory `dir`: those in it and in its subdirectories, at any depth. So libraries can live in directories of their own, which several programs add. A file that two directories reach, or one directory twice, is compiled once.
6. `build::optimize{ &b, exe, level }` compiles the executable's C at optimization level 0 to 3 (`-O0` to `-O3`) instead of 1. The other flags stay (internals.md, How ctxlang maps to C). `build::trace_calls{ &b, exe, on }` says whether the executable keeps its call paths (§15, Call paths, rule 7). Unsaid, it keeps them at levels 0 and 1 and not at 2 and 3, where they would cost a few percent of the speed the level was chosen for, and its test build (§20) keeps them at every level. The last call for an executable decides, for its test build too.
7. `link` adds a library (`-l`), `framework` a macOS framework, and `lib_path` a directory to find libraries in (`-L`).
8. Paths are relative to the directory `build.ctx` is in, and may leave it through `..`. Errors name an executable's files by their paths from the working directory, without `.` or `..` (`lib/formats/gff.ctx`). A file named `build.ctx` is never one of an executable's files.
9. Names, roots, directories, libraries and paths can't be empty or hold a tab or a line break, a name is ASCII letters, digits, `_`, `-` and `.` and doesn't end in `.`, so that names Windows takes for one another differ only in ASCII's case, a generated file's name (rule 13) is ASCII letters, digits, `_` and `-` and isn't `build` or `api` in any case, and a level is 0 to 3: the build panics.
10. `ctxc run PATH [-- ARGS...]` builds the program at PATH (a `.ctx` file, or a directory, with or without a `build.ctx`) and runs its first executable; `ctxc exe PATH -o OUT` writes that executable to OUT; `ctxc test PATH [ARGS...]` builds it to run its tests instead (§20); `ctxc check PATH` reports its errors and builds nothing (§21). Only ctxc and a C compiler are needed (internals.md, "Working on ctxc"). `ctxc graph DIR GEN LIST` runs the build program as `run` does and writes what it describes to LIST, and the files it generates to GEN, for tools that build the executables themselves (ctxc/drive.ctx). `ctxc where PATH NAME` says where the program at PATH declares NAME, `a::b::f` or a name in any namespace, with its module and where it is visible; `ctxc api PATH FOLDER` writes FOLDER/api.ctx, a first contract for a folder from what the rest of the program names of its files: each fn's signature with the errors it is inferred to fail with, and what is complete without a body moved from the files (§10, Modules, rule 3), a starting point rather than one kept up to date.
11. A build writes only under ctxc's home, in `build/run`, in a directory of the program's own, which its absolute path names: ctxcs building different programs at once don't meet. A big program's C is several units, grouped by the files that declare their functions, which are compiled at once; a unit whose C, runtime, C compiler and flags are the same as when it was last built isn't compiled again, so an edit recompiles only the units of the files it touched, and those that call a small function it changed, which each hold a copy of it for C to inline (ctxc/drive.ctx, ctxc/emit_c.ctx).
12. `#build::sources{ dir }` on the build program's `fn build` makes the `.ctx` files under directory `dir` its files too, besides build.ctx, found as rule 5 finds an executable's, with paths as rule 8 says. So a code generator can be a library of its own, which build programs share. `fn build` may have several. They are the build program's files only, not its executables'. ctxc reads the attribute (std's `build::sources`, §17) from build.ctx before it compiles the build program, so `dir` must be a string literal; one that names no directory, or one without `.ctx` files, and the attribute on anything else in build.ctx, are errors at their positions.
13. `build::gen_file{ &b, exe, name, text }` gives the executable a file of ctxlang source, `NAME.ctx`, that holds `text`, as if it were in one of its directories: for modules (§10, Modules, rule 1), in its executable's root. ctxc writes it in the program's build directory (rule 11), as `gen/EXE/NAME.ctx`, never in the source tree, and errors in it name that path; the executable is compiled from ctxc's own copy of the text, so another ctxc building the same program at once can't change what it compiles. It is written only when its text changed; the other `.ctx` files in its executable's directory are removed, and the directory of an executable that generates none, once it is empty. One executable can't have two files of one name, nor on Windows names that differ only in case. The build program never sees the files it generates: they are only its executables'. A `Build` writes no file itself: the text goes to ctxc with the build's description (std/build.ctx), and ctxc writes it.
14. `build::declarations{ &b, &fs, &mem, &heap, realloc, exe }` gives the declarations of exe's files as they are at the call: its root's, and those of the directories `add_sources` gave it before, found as rule 5 finds them, with paths as rule 8 says; never its generated files, so a generator never sees its own output. It parses them and checks nothing: a `build::Decl` is a struct, union, extern union, enum, fn, extern fn, const, type, capability or error (its `kind`), with its name, the namespaces around it (`path`, as `game::world`), its generic parameters' names, its attributes, its fields (a fn's context fields, with `mut`), each with its attributes and a struct's with its default, its variants, its types and values as text, and its file and position. A type is spelled one way (`*mut T`, `list::List(T, S)`, `&fn{ a: T } -> R`), and anything else written, an attribute's field too, is its tokens as written, with one space between two that anything came between, so a string literal, multi-line or not, keeps its text; a string, integer, character or bool literal's value is there as well. Nothing is resolved, so a name may be one the build program has yet to generate.
15. A syntax error doesn't stop it: the declarations around it are there, and the errors are in `diags`, by file, line and column. It fails with `fs`'s errors for a directory or file it can't read, and with `alloc::out_of_memory`. Its result is in memory from `realloc`; parsing takes memory of its own, from `mem::reserve`, which it keeps for its next call.
16. A build program has what `declarations` needs with std: std/build/'s files and ctxc's lexer and parser (ctxc/source.ctx, diag.ctx, lexer.ctx, syntax.ctx and parser.ctx) are among std's files (§17) in it, and in no other program. Any program whose entry is `fn build` (rule 2) is one, however ctxc builds it: `ctxc run build.ctx` runs one as a program of its own, whose graph goes to standard output and whose paths are from the working directory. So `declarations` is in std's `build`, and a namespace of the program's named like one of ctxc's (`parser`, `syntax`, `lexer`, `tok`, `source`, `diag`) shadows it (§10, rule 4).
17. `build::deny_unchecked{ &b, exe, except }` makes the unchecked operations (§13) errors in the executable's files, those of directories added after the call too, but for the files under each directory of `except`, a `[][]u8`, at any depth. `except = []` denies them in every file. Each directory is named as `add_sources` names one (rule 8) and must hold at least one of the executable's files: one that holds none, misspelt or since removed, stops the build, which names it, so the list never excepts more than a reader of it sees. A file the build program generates (rule 13) is under no directory of the program's, so it is always denied: unchecked code is written in a directory, where review finds it, and generated code calls it. std's files are never denied. With several calls for one executable, a file is excepted if any of them excepts it. An executable without a call may use the operations anywhere, as every program did before there was one; the build program's own files (rule 12) are no executable's, and are never denied.

<!-- context:
// file: build.ctx
...
// file: tools/describe.ctx
namespace describe {
    fn generate { mut heap: arena::Arena, decls: []build::Decl } -> []u8 {
        let mut b = utf8::builder{ realloc = arena::alloc, &heap }
        _ = @fmt(&b, "namespace fields {{")
        for d in decls {
            if d.kind == build::Kind::structure { _ = @fmt(&b, " fn {} {{}} -> usize {{ return {} }}", d.name, d.fields.len) }
        }
        _ = @fmt(&b, " }}")
        return utf8::view{ b }.bytes
    }
}
// file: src/main.ctx
struct describe {}
struct Color { r: u8 }
#describe
struct Paint { color: Color, coats: u32 }
fn main {} { _ = fields::Paint{} }
-->
```ctx
// examples/gen/build.ctx: describe::generate, a library of the build program's, writes a fn for
// each struct of src's marked #describe that prints its fields
#build::sources{ dir = "tools" }
fn build { mut b: Build, mut fs: Fs, mut mem: Mem } {
    let exe = build::exe{ &b, name = "colors", root = "src" }
    let pages = mem::reserve{ &mem, size = 1073741824 } ifnull { @panic("out of memory") }
    let mut heap = arena::new{ buf = pages }
    // For `#describe struct Paint { color: Color, coats: u32 }` in src/main.ctx: a Decl of kind
    // structure named "Paint", with an Attr named "describe" and fields "color", of type
    // "Color", and "coats", of "u32". Color, which this program generates, needn't exist yet.
    let found = try! build::declarations{ &b, &fs, &mem, &heap, realloc = arena::alloc, exe }
    build::gen_file{ &b, exe, name = "fields", text = describe::generate{ &heap, decls = found.decls } }
}
```

## 20. Tests

<!-- context:
namespace cfg {
    struct Entry { key: []u8, value: u32 }
    error no_equals{ at: usize }
    fn parse_line { line: []u8 } -> !Entry {
        for c at i in line {
            if c == '=' { return Entry{ key = line[0..i - 1], value = 12 } }
        }
        return no_equals{ at = line.len }
    }
    fn field { line: []u8, index: usize } -> []u8 { return line[index..index + 1] }
}
...
-->
```ctx
// cfg/cfg_test.ctx, beside cfg/cfg.ctx
namespace cfg_tests {
    #test
    fn reads_a_key_and_its_value { mut t: Test } -> ! {
        let entry = try cfg::parse_line{ line = "depth = 12" }
        @expect(&t, entry.key == "depth")
        @expect(&t, entry.value == 13)
    }

    #test
    fn a_line_without_a_value { mut t: Test } -> ! {
        let entry = try cfg::parse_line{ line = "depth" }
        @expect(&t, entry.value == 0)
    }

    #test{ panics = "out of bounds" }
    fn a_field_past_the_end_panics {} { _ = cfg::field{ line = "a b", index = 2 } }
}
```

```text
$ ctxc test cfg
cfg/cfg_test.ctx:6: fail: cfg_tests::reads_a_key_and_its_value: entry.value == 13: 12 == 13
cfg/cfg_test.ctx:10: fail: cfg_tests::a_line_without_a_value: error: cfg::no_equals{ at = 5 }
tests: 3 run, 1 passed, 2 failed, 0 skipped, 0 not selected, 2 checks
```

1. `#test` on a fn makes it a **test**: a fn with a body and no generic parameters. Its context is capabilities without fields (§15), which are supplied as `main`'s are, so a test declares what it touches: one that takes no `Fs` can't reach a file. One of them is a `Test` (rule 2), which its checks report to. Its result is nothing, or a bare `!` for the errors it passes up with `try`. Anything else in its context or as its result is an error at the fn. A test is a fn like any other: it is checked in every build, other code may call it, and a build that isn't a test build never reaches it from `main`, so it is not in the executable.
2. `Test` is std's capability for a test's checks (§17, `test`). Only a test and the `#test_main` fn (rule 11) receive one; `main`, `build`, a `#start` fn and a `#panic` fn can't take it. A test passes it down to the functions that check for it, as any capability: `fn same_table { mut t: Test, a: Table, b: Table }`. It includes an `Io` (§15, rule 9), where a failure is written as it happens.
3. A test checks with `@expect(&t, c)` and `@require(&t, c)` (§13, Checks). A test **passes** if it returns without an error, having made at least one check, with every check it made holding. It **fails** if
   - an `@expect` didn't hold: the test goes on, so one run shows every check that fails;
   - a `@require` didn't hold: the test ends there, with the failures before it shown too. It is for a check that the next lines need, as `@require(&t, table.rows.len > 0)` before `table.rows[0]`, which would otherwise panic and hide what was wrong;
   - it returns an error, which is written as `main`'s is (§15, Entry point, rule 4);
   - it panics, or its process ends in any other way, or it runs past the time limit (rule 8). A test that exits by itself with code 0 failed too: a test passes by returning;
   - it made no check. A test passes by what it checked: one that only runs code says so with a check of what the code gave, and one that forgot its checks is not reported as passing. A `@require` that held is a check.
4. `#test{ panics = "text" }` is a test that passes by panicking: with a message that contains `text`, a string literal. It fails if it returns, or panics with another message, or ends at a `@require` that doesn't hold, with that `@require`'s line. It needn't take a `Test`.
5. A **skipped** test is neither passed nor failed: it lacks something it needs, and says what. It has one line, `FILE:LINE: skip: NAME: WHY`, at the test fn's name, and is counted in the summary (rule 9), so a run never has fewer tests without saying so.
   - `test::skip{ &t, why = "no game install" }` (§17, `test`) skips the running test from inside, once it has found what it lacks. **The test ends there,** as at a `@require` that doesn't hold (§13, Checks, rule 7): by its process ending, from whatever function calls it, and no `defer` runs. `skip` is a function, so the checker doesn't know that it never returns: where a path must end, as in an `ifnull` block, a `return` follows the call.
   - What the test did before a skip doesn't decide it: the checks that held are not a pass, though the summary counts them among the checks made (rule 9), it needs no check, and what it wrote is dropped. A check that didn't hold does decide it: the test has failed, and a skip after that leaves it failed, with its failures' lines and no skip's line.
   - `#test{ skip = "why" }` skips the test where it is declared: it isn't run, and has no process. `why` is a string literal, and not empty. The fn is checked as any test, and takes a `Test`. With `panics` too, `#test{ skip = "why", panics = "text" }`, it is skipped: `panics` says how it passes once it runs again. A test that must panic and calls `test::skip` before its panic is skipped as well.
   - A skip is not a failure. The exit code is 0 if no test failed, also if every selected test was skipped: the skips' lines and `0 passed` in the summary say so. `--no-skips` makes it 1 if a test was skipped, for a run that must lack nothing, as on a machine that is known to have the game.
   - Under a `#test_main` fn that runs tests in its own process (rule 11), `test::run_here` writes the line of a `#test{ skip = "why" }` to standard error and gives `test::SKIPPED`, 77, the code other runners (automake, meson) read as skipped. `test::skip` ends that process with the same code, so the tests after it don't run, as after a `@require` that doesn't hold, and the run is not taken for a pass.
6. `ctxc test PATH [ARGS...]` builds the program at PATH, a `.ctx` file or a directory with or without a `build.ctx`, as `ctxc run` does (§19, rule 10), but as a **test build**, and runs it with ARGS. In a test build the program's entry point is the `#test_main` fn (rule 11), std's `test::main`, in place of `main`, which needn't exist: a directory of a library's files and its tests is a program to test. The tests are the `#test` fns of the first executable's files (§19), in the order of its files and, in a file, of their declarations. std's files are never among them: std's own tests are a program of their own, `std/tests`. The test build is kept beside the program's own build, under another name, and doesn't replace it.
7. **Each test runs in a process of its own**: the test build's executable, started again for that test alone. So a panic ends one test and fails it, with its message, and the others run; a test never sees what another left in a capability's static (§15, rule 13), the only state that outlives a call; and the tests run at once, as many as the machine has processors, or `--jobs N`. The test's standard input is empty. Its standard output and standard error go to one file beside the executable, in the order they were written, which the runner reads when the test ends and then removes: a passing test's output is dropped, a failing test's is printed, and of a skipped test's only its skip's line. The last line a test's process writes is its report to the runner, `FILE:LINE: checks: NAME: N`, the number of checks it made, which the runner takes off the output and adds up (rule 9).
8. A test that runs longer than 60 seconds, or `--timeout SECONDS`, is ended and fails; `--timeout 0` sets no limit. The time is counted in the runner's own waits, so a test is given at least that long.
9. **Output.** The runner writes to standard output, one line for each failure and for each skipped test, in the tests' order whatever order they ended in, and then one summary line. A model or a tool reads it by line:

   ```text
   FILE:LINE: fail: NAME: TEXT: LEFT OP RIGHT            a comparison that didn't hold
   FILE:LINE: fail: NAME: TEXT                           any other condition that didn't hold
   FILE:LINE: fail: NAME: required: TEXT: LEFT OP RIGHT  a `@require`'s comparison that didn't hold: the test ended there
   FILE:LINE: fail: NAME: required: TEXT                 any other condition of a `@require`
   FILE:LINE: fail: NAME: error: ERROR                   the test returned an error
   FILE:LINE:COL: fail: NAME: panic: MESSAGE             the test panicked
     at FUNCTION (FILE:LINE:COL)                         under a panic's line: its call path, up to the test fn
     called from FUNCTION (FILE:LINE:COL)                under a check's line: the calls that led to its function
   FILE:LINE: fail: NAME: no check ran: a test passes by the `@expect`s it makes
   FILE:LINE: fail: NAME: timed out after N s
   FILE:LINE: fail: NAME: its process ended with exit code N
   FILE:LINE: fail: NAME: its process didn't start: ERROR
   FILE:LINE: fail: NAME: it didn't panic: a panic with `text` was expected
   FILE:LINE: fail: NAME: its panic's message doesn't contain `text`
   FILE:LINE: skip: NAME: WHY                            the test was skipped (rule 5)
   tests: N run, P passed, F failed, K skipped, S not selected, C checks
   ```

   - NAME is the test fn's name with its namespaces, `twoda_tests::a_short_row_takes_the_default`. FILE is the file as an error of the compiler's names it (§19, rule 8).
   - A check's FILE:LINE is the `@expect`'s or the `@require`'s, and TEXT is its condition as written, on one line. LEFT and RIGHT are the values of the comparison's two sides (§13, Checks). A panic's position is the panic's own, as std's report gives it (§15, Entry point, rule 6). Every other line is at the test fn's name, a skip's too, wherever `test::skip` was called.
   - Every failure's line has `: fail: NAME: ` in it, and no other line the runner writes does. A failing test's other output, what it printed itself, follows its process's order among those lines, as it was written.
   - **Call paths.** A test build keeps its call paths, at any optimization level, unless its build program turns them off (§15, Call paths, rule 7). Under a panic's line is the panic's path, as the test's process wrote it, which ends at the test fn: what runs the test isn't in it. Under the line of a check that didn't hold in a function the test called are the calls that led there, `called from` lines, up to the test fn (§13, Checks, rule 9); a check in the test fn has none. These lines start with two spaces, so no failure's line is one.
   - A skipped test has its one line, the only kind with `: skip: NAME: ` in it. The words are the suite's runner's for a case it skips (ctxlang/tests/README.md).
   - With `-v`, each passing test has a line too: `FILE:LINE: pass: NAME`.
   - The summary is the last line: of the N tests the arguments selected, P passed, F failed and K were skipped, so N is P + F + K, a skipped test counting among those run as in the suite's summary; and S of the program's tests were not selected.
   - C, at the summary's end, is how many checks those tests made: every `@expect` and `@require` that was evaluated, held or not, in the test or in a function it passed its `Test` to, each as often as it ran. It is what a program that counted for itself printed as `49 checks`, and the line before it reads as it did without it. The word is `checks` for every number.
   - A test reports its checks as it ends: by returning, at a `@require` that doesn't hold, or at a `test::skip`. A test whose process ends in another way reports nothing, and none of its checks are in C: one that panicked, also one that must panic, one that was ended at the time limit, and one that exited by itself. Each of those but a test that must panic has a failure's line, so C is every check of a run without such lines and without tests that must panic, and at least C were made otherwise.
10. **Arguments and exit code.** `ctxc test PATH [OPTION...] [FILTER...] [-- ARGS...]`: what follows the first `--` is the tests' own (rule 13), and the rest is the runner's. Every argument of the runner's that doesn't start with `-` is a filter: a test is run if its NAME contains one of them, and every test is run without one. `--list` writes `FILE:LINE: NAME` for each test that is selected, and runs none. The exit code is 0 if no selected test failed, and at least one was selected; 1 if a test failed, or with `--no-skips` if one was skipped (rule 5), and also if none was selected, with a last line that says why, so that a mistyped filter or a program without tests is not taken for a pass: ``tests: 0 run: no test's name contains `twoda_x`, of 12`` or ``tests: 0 run: the program has no `#test` fn``; and 2 for an option the runner doesn't know. A failure of the build is ctxc's own, with its errors (exit code 1) and no summary line.
11. `#test_main` on a fn makes it what a test build runs in place of `main`: a fn with a body and no generic parameters that returns the exit code, an `i32`. Its context is capabilities without fields, a `Test` among them if it wants, and any of these read-only fields, which the compiler supplies: `args: Args`, as `main`'s, every argument after PATH; `count: usize`, the number of tests; `case: &fn{ index: usize } -> test::Case`, test `index`'s name, file and line, its file's directory (rule 12), whether it must panic and with what, and whether it is skipped and why (§17, `test`); and `run: &fn{ index: usize } -> i32`, which calls test `index` with its capabilities and gives 0, or 1 after writing the error it returned, as `main`'s is written after `FILE:LINE: fail: NAME: `. `run` only calls the test: whether it passed is what std's `test::run_here{ &t, c, index, run }` gives (§17, `test`), which sets the test's name for its failures' lines and its directory, runs it, and looks at what it checked: `test::checks{ &t }` is then how many checks it made, for a runner that adds them up. std declares one `#test_main` fn, `test::main`, which is rules 7 to 10; a program's own replaces it, as its `#start` fn replaces std's (§15, Entry point, rule 7), for a runner of another kind, such as one that runs every test in one process with `run_here`, which the first `@require` that doesn't hold ends (§13, Checks, rule 7), or the first `test::skip` (rule 5). Two in the program are an error.
12. **A test's own directory.** `test::dir{ &t }` (§17, `test`) is the directory of the source file that the running test's `#test` fn is in, a `[]u8`: where a test finds a file kept beside it, wherever `ctxc test` was run from.

    <!-- context:
    #test
    fn reads_rows { mut t: Test, mut fs: Fs, mut mem: Mem } -> ! {
        let pages = mem::pages{ &mem, size = 65536 } ifnull { return alloc::out_of_memory }
        let mut heap = arena::new{ buf = pages }
        ...
        @expect(&t, data.len > 0)
    }
    -->
    ```ctx
    // lib/formats/twoda_test.ctx reads lib/formats/rows.2da
    let mut path = utf8::builder{ realloc = arena::alloc, &heap }
    try @fmt(&path, "{}/rows.2da", test::dir{ &t })
    let data = try fs::read_all{ &fs, &heap, realloc = arena::alloc, path = utf8::view{ b = path }.bytes }
    ```

    - It is an absolute path, with `/` between its parts on every platform and none at its end, so a file in it is `DIR/NAME`. It is made of the working directory of `ctxc test` and the file's name as the compiler was given it, the FILE of the test's lines (rule 9), without looking at the file system: a link in it is not followed.
    - It is the directory of the test's file, whichever function asks: a helper in another file, which the test passed its `Test` to, gets the test's directory and not its own. Each file of the program has its own directory, also one that `build::add_sources` adds from elsewhere (§19).
    - A test in a file that `build::gen_file` generates (§19) is given the directory ctxc wrote that file in, under the program's build directory, where it has no other file. A generator whose tests read a file writes that file's path into the text it generates.
    - It is fixed when the test build is made: a string in the executable. `ctxc test` builds before it runs, so the path is that of the checkout it runs in, and after a checkout is moved its next `ctxc test` builds again.
    - The working directory is not changed, and stays that of whoever ran `ctxc test`: a test executable has tests from many directories, and a relative path in an argument (rule 13) means what its writer meant. Only a test's own file is the same on every machine and in every run.
    - A `#test_main` fn reads it as `test::Case`'s `dir`, and `test::run_here` sets it for the test it runs.
13. **Arguments for the tests.** `ctxc test PATH [OPTION...] [FILTER...] -- ARGS...` gives ARGS to every test, which reads them with `test::args{ &t }` (§17, `test`): a `[][]u8`, as `main`'s `args` (§15, Entry point). They are for what a run names and the source can't know, as where a game is installed:

    ```ctx
    #test
    fn the_install_has_its_key_file { mut t: Test, mut fs: Fs, mut mem: Mem } -> ! {
        let args = test::args{ &t }
        if args.len == 0 { test::skip{ &t, why = "no game install: give its directory after `--`" } }
        let pages = mem::pages{ &mem, size = 65536 } ifnull { return alloc::out_of_memory }
        let mut heap = arena::new{ buf = pages }
        let mut path = utf8::builder{ realloc = arena::alloc, &heap }
        try @fmt(&path, "{}/chitin.key", args[0])
        let key: []u8 = try fs::read_all{ &fs, &heap, realloc = arena::alloc, path = utf8::view{ b = path }.bytes }
        @require(&t, key.len >= 8)
        @expect(&t, key[..8] == "KEY V1  ")
    }
    ```

    ```text
    $ ctxc test formats
    formats/key_test.ctx:2: skip: the_install_has_its_key_file: no game install: give its directory after `--`
    tests: 6 run, 5 passed, 0 failed, 1 skipped, 0 not selected, 14 checks
    $ ctxc test formats key_file -- F:/Games/swkotor
    tests: 1 run, 1 passed, 0 failed, 0 skipped, 5 not selected, 2 checks
    ```

    - Everything after the first `--` is ARGS, whatever it looks like: an option, a test's name, an empty word, a second `--`. The runner's options and the filters come before it. Without a `--`, or with nothing after it, `test::args` is empty.
    - Every test of the run is given the same ARGS, each in its own process; none are for one test alone. A test that finds an argument missing skips (rule 5) or fails, as it says: nothing is a pass for lack of one. A relative path among them is relative to the working directory, which is that of whoever ran `ctxc test` (rule 12).
    - A `#test_main` fn (rule 11) has every argument after PATH in its `args`, the `--` too. `test::own_args{ args }` is those before the first `--`, and `test::pass_args{ &t, args }` hands the tests those after it: until it is called, they have none.
    - The environment is not a second way the runner gives: it reaches a test as it reaches any program, through a `Proc`, with `proc::env{ &proc, name }` (§17, `proc`), and a test's process has the environment `ctxc test` was run with. An argument is in the command, where a log shows it and a typing mistake is seen; a variable suits what a machine sets once for every run.
14. Not supplied, each for its reason:
    - **A temporary directory.** A test that writes files takes an `Fs`, and makes and removes its own directory. A runner's would have to be removed as a tree when a test that crashed left files in it, and std's `fs` removes one empty directory at a time on purpose (§17, `fs`).
    - **A leak check.** std's one allocator is the arena (§17, `arena`), which frees everything at once, so there is nothing for a counting allocator to wrap. A program with a heap of its own checks it as any value: `@expect(&t, heap.live == 0)`.
    - **Tests over a table of cases,** one fn that the runner calls once for each row. A test loops over its table, and an `@expect` in the loop names the case in its condition's values.

15. **Results as JSON.** `ctxc test PATH --json`, `--json` being one of the runner's options (or before PATH, as for `ctxc run`), writes the results as JSON on standard output, in place of rule 9's lines: an object on a line for each test, in the tests' order, passed ones too, and one for the run. The build's diagnostics are JSON as well, on standard error (§21, rules 9 to 11).

    ```text
    {"type":"test","name":"cfg_tests::reads","file":"cfg/cfg_test.ctx","line":4,"outcome":"fail","checks":2,"failures":[{"file":"cfg/cfg_test.ctx","line":9,"message":"text.len == 42: 17 == 42"}],"output":[]}
    {"type":"test","name":"cfg_tests::finds_the_game","file":"cfg/cfg_test.ctx","line":14,"outcome":"skip","checks":0,"reason":"no game install"}
    {"type":"tests","run":2,"passed":0,"failed":1,"skipped":1,"not_selected":0,"checks":2}
    ```

    - **A test's record** has `type`, `"test"`; `name`, `file` and `line`, the test fn's; `outcome`, `"pass"`, `"fail"` or `"skip"`; and `checks`, how many it reported (rule 9). A skipped one has `reason`, what its line says after its name. A failed one has `failures`, an array with an object for each of its failure lines, `file`, `line` and `message`, the line's text after `: fail: NAME: `, and so `panic: index 4 out of bounds for length 2`, `timed out after 60 s` or `no check ran: ...` for a failure that isn't a check's; and `output`, an array of the other lines it wrote, as strings, in order.
    - **A failure's call path** is in its object, where the text form has lines under the failure's: `path` for a panic, the whole path from the function the panic is in, and `called_from` for a check, the calls that led to its function; neither where there are no such lines. Each is an array, innermost first, of objects with `kind`: `"call"`, with `function`, `file`, `line` and `column`, the last two 0 where the position isn't known; `"start"`, the same for where a task was started; `"c_code"`, C code that called a callback; and `"omitted"`, with `count`, for the middle of a long path. The lines aren't in `output`.

      ```text
      "failures":[{"file":"t.ctx","line":3,"message":"a == b: 3 == 2","called_from":[{"kind":"call","function":"helpers::all_twos","file":"t.ctx","line":7,"column":27},{"kind":"call","function":"in_helpers","file":"t.ctx","line":19,"column":22}]}]
      ```
    - **The run's record** has `type`, `"tests"`, and `run`, `passed`, `failed`, `skipped`, `not_selected` and `checks`, the numbers of rule 9's summary. When no test ran (rule 10) they are 0 and `reason` says why, as the line does.
    - **With `--list`,** each test that is selected has a record with `type`, `name`, `file` and `line`, and no outcome.
    - **A check's two sides are in `message`,** not in fields of their own: `text.len == 42: 17 == 42` is the condition as written and then the values, each written by the program's own writers (§13, Checks, rule 3) into the one line, and either may hold the `: ` or the operator that would separate them. A test that needs a value read by a machine compares it in a condition of its own.
    - The exit codes are rule 10's.

## 21. Checking and diagnostics

```text
$ ctxc check tools/viewer
tools/viewer/main.ctx:14:17: error: literal 300 does not fit in u8
lib/formats/gff.ctx:212:9: error: unknown name `read_feild`
check: 2 errors; not checked until the program has no other error: the order of a call's fields, what tasks borrow, consts computed by running code
```

1. `ctxc check PATH` checks the program at PATH and reports its errors, and builds nothing: the front end runs, and neither the C backend nor a C compiler. PATH is what `ctxc run` takes (§19, rule 10): a `.ctx` file, or a directory with or without a `build.ctx`. The exit code is 0 for a program without errors, 1 for one with an error or one that can't be read, and 2 for a command that isn't `ctxc check PATH`.
2. **A diagnostic** is a line on standard error, `PATH:LINE:COL: error: MESSAGE`, the same from every command: PATH as the file was named to the compiler, which for a directory is from the working directory; LINE and COL from 1, COL counted in characters. An error about the whole program, as a missing `main`, is at `1:1` of its first file. Some have notes under them (rule 8), and `--json` writes the same as JSON (rule 9).
3. **With a build program,** it is compiled and run first, as `ctxc run` does it, since only running it says which executables there are and of which files (§19): this is the one thing `check` builds, and it is built again only when build.ctx or a file it is made of changes. Then **every** executable it describes is checked, where `run` and `exe` stop at the first that has an error: each with the files generated for it, which are written to the build directory as for `run` so that an error in one names a file to open (§19, rule 13), and with the unchecked operations denied where its build program denies them (§13). An error in a file that several executables share is reported once. An error in the build program itself is all that is reported: nothing says what the executables are. Without a `build.ctx`, `check` writes no file and makes no directory.
4. **As `run` and as `test` build it.** `check` reports what `ctxc run` and `ctxc test` (§20) would each report, in one pass: a `#test` fn is checked in every build, and for `check` so is what only a test build has, the `#test_main` fn as the entry point and the writing of the error a test returns. A program with `#test` fns and no `main` is a program to test, and has no error for that; one with neither has `no `fn main` entry point`.
5. **Every error.** The compiler doesn't stop at an error, in any command. A file that doesn't parse is parsed on from its next statement or declaration, and the other files are checked with what it declares; every declaration is checked, and every function's body, to its end. `run`, `exe` and `test` show the first 100 and then say so, `ctxc: more than 100 errors: these are the first 100, and `ctxc check` reports every one`; `check` shows every one. The errors come in the order the compiler finds them: syntax errors first, file by file, then declarations, then bodies, then what is checked over whole functions. What is held back, so that one mistake isn't reported several times over or as something it is not:
    - **What follows from another error** isn't reported: an expression whose type couldn't be found is used without further errors, the same error at the same place is reported once, and rule 7's causes have one error each.
    - **In a body that has an error,** what is checked along its paths is left out: a local read before it is assigned or assigned twice (§11, Initialization), an address that escapes (§14), and a call's places that overlap (§3.1). They are reported once the body's other errors are gone.
    - **Three checks wait for a program without errors,** because they read every function the program reaches: the order of a call's fields and the places a call may be given together (§3, §3.1), what a task borrows (§15, Tasks), and the consts and literals computed by running code (§14). An error from one of the first two still holds back the last.
6. **The last line** of `check` counts what it reported, on standard error: `check: no errors`, or `check: N errors`, followed, if any of rule 5's three checks didn't run, by which: `; not checked until the program has no other error: the order of a call's fields, what tasks borrow, consts computed by running code`. So a program can take three runs of `check` to be shown clean, and the line says when another is due. If some of the errors have a fix that `--fix` applies (rule 13), the line ends with how many: ``; 2 of them have a fix that `ctxc check --fix` applies``.
7. **One cause, one error.** Where one mistake would be reported at every place it shows, the error is at the cause, or at the first place with a count:
    - **A namespace no file declares.** A name before a `::` that nothing declares, `mini` in `mini::start{}`, is one error at its first use, however many uses there are: ``unknown type or namespace `mini`, used here and at 5 more places``. The usual cause is a build.ctx that doesn't add a library's directory, so the driver looks for a file that declares `namespace mini` at its top and isn't one of the program's, and the error goes on: ``: `lib/mini/mini.ctx` declares `namespace mini`, and isn't one of this executable's files: add its directory in build.ctx, with `build::add_sources{ &b, exe, dir = "../lib/mini" }` ``, `dir` being from build.ctx's directory (§19, rule 8). It looks under build.ctx's directory and under the directory that each of the executable's directories is in, in at most 2000 directories, none of them named with a `.` first, and names the first file it finds. For a directory without a build.ctx it looks below the directory, and for a program of one file beside it, and says that the file isn't part of such a program. A name alone, `Queue`, is reported at each use: each may be a different slip.
    - **A merge conflict.** A line that starts with `<<<<<<<`, with its `=======` and `>>>>>>>` lines after it, is one error at that line, ``unresolved merge conflict, to the `>>>>>>>` at line 6: keep one side and delete the marker lines (the first side was checked, and the rest skipped)``: the first side is read as the file's text, so the rest of the file is still checked, and the lines from the `=======` (or the `|||||||` of a merge that shows the common ancestor) to the `>>>>>>>` aren't read. Any other line that starts with seven of `<`, `=`, `>` or `|` and then a space or the line's end is ``a merge conflict's marker was left here: delete the line``, and is skipped. No program has such a line.
    - **Syntax that hides what follows.** A block comment that doesn't end is one error, without one for each `}` it hid. A `(` or `[` that isn't closed before its block's `}` is one error, and the `}` still closes the block. Fields a line each without commas, of a struct or of a function's context, are one error for each missing comma, ``expected ',' before the next field, `y` ``, and stay fields. A body with a syntax error isn't also reported as not returning on every path, nor a program whose file has one as having no `main`. A type argument that didn't parse, as the `3` of `f(3)`, isn't also counted against how many `f` takes.
    - **`&p` where `p` is the pointer wanted:** ``take{ &heap }`` for a `mut heap: Heap`, with `heap` a `*mut Heap`, is ``` `heap` is a *mut Heap already, which is what `mut heap` takes: pass it as it is, without the `&` ```, in place of two errors, that `heap` isn't a mutable place and that a pointer to a pointer isn't a pointer.
    - **A form of another language** is one error that says what to write in ctxlang, and the rest is checked as if that were written, so none follows from it:

      | Written | Is | Error |
      |---|---|---|
      | `f(a, b)`, `f()` | a call | ``a call names its fields, in braces: write `add{ a = 1, b = 2 }` ``, with f's fields in their order, `&` before an argument whose field is `mut` |
      | `Point(1, 2)` | a struct's literal | the same, ``a struct's literal names its fields, in braces: ...`` |
      | `println("hi")`, `print`, `puts`, `printf`, where no function has the name | printing | ``there is no `println`: write `io::println{ &io, s = "hi" }`, with `mut io: Io` among the function's fields`` |
      | `x.f(...)` | a method call | ``there are no methods in ctxlang: call a function with `x` as one of its fields, ...``; `s.len()` is ``` `len` is a field, not a method: write `s.len`, without `()` ``` |
      | `!b`, `a && b`, `a \|\| b` | `not b`, `a and b`, `a or b` | ``` `&&` is the word `and` in ctxlang: write `a and b` ```; `&&` and `\|\|` bind as `and` and `or` do |
      | `x += n` and every binary operator's, `x++`, `x--` | `x = x + n`, `x = x + 1` | ``there is no `+=` in ctxlang: write `x = x + n` `` |
      | `x as T`, `(T)x` for a primitive type T | `@as(T, x)` | ``a conversion is the builtin `@as` in ctxlang: write `@as(T, x)`, not `x as T` `` |
      | `c ? a : b` | `if c { a } else { b }` | ``there is no `? :` in ctxlang, since `if` has a value: ...`` |
      | `p->x`, `*p` | `p.x`, `p.*` | ``a field through a pointer is `p.x` in ctxlang, as on a value: ...`` |
      | `fn f(a: i32)`, `fn f()` | `fn f { a: i32 }`, `fn f {}` | ``a function's fields are in braces in ctxlang: write `fn f { a: i32 }` ``; a generic error set, `fn f(E: error)`, named in upper case, is still one |
      | `fn f -> T` | `fn f {} -> T` | ``a function without fields still has its braces in ctxlang: ...`` |
      | `enum K { a, b }` | `enum K: u8 { a, b }` or `union K { a, b }` | ``an enum is an integer type, and names which: ...``, checked on as a `u8` |
      | `var x = 0`, `loop { }` | `let mut x = 0`, `while true { }` | ``a local that changes is `let mut` in ctxlang: ...`` |
      | `io` as a value in a function without that field, where `Io` is a capability | the field | ``` `io` is a namespace here: the capability is a field, so add `mut io: Io` to `hello`'s fields, and pass it in, `hello{ &io }` ``` |
      | `P{ x: 1 }`, `f{ a: 1 }` | `P{ x = 1 }` | ``a field is given with `=` in ctxlang: write `x = 1`, not `x: 1` `` |
      | `K.a`, `io.println` | `K::a`, `io::println` | ``a variant is reached with `::` in ctxlang: write `K::a` ``; for a namespace's member, the same, and where a local has the namespace's name and lacks the field, the error says the local is one |
      | `"a" + b` | the parts written into a `utf8::Builder` | ``text doesn't join with `+` in ctxlang: write the parts into a `utf8::Builder`, `try @fmt(&b, "{}{}", a, b)` ``, for a `[]u8`, a string literal or a `utf8::String` |
      | `string`, `str`, `String`, `int`, `uint`, `long`, `short`, `char`, `byte`, `float`, `double`, `boolean`, `size_t`, `void` as a type | ctxlang's type | ``there is no `int` in ctxlang: write `i32`, or another of ...`` |
      | `let` or `var` where declarations go | a local of `main`, or a `const` | ``there is no state at top level in ctxlang: ...``, each one |

      `f(a, b)` with names alone parses as generic arguments (§9, rule 2); for a function without generic parameters it is the same error as `f(1, 2)`.

8. **Notes.** An error about two places has the other one as a **note**: a place and a message, under the error, indented by two spaces, in the order given here.

    ```text
    lib/a.ctx:4:5: error: returned value holds the address of local `v`
      lib/a.ctx:3:5: note: `v` is declared here
    ```

    - **An address that escapes** (§14): where the local is declared, ``` `v` is declared here ``` (for a context field, ``` `v` is a context field, declared here ```; for an array literal's hidden array, `the array literal is here`), and for a store into a local or a caller's place that outlives it, where that one is declared, after it. So have a bound function stored in a local that outlives a place it holds (§6), and a branch's value that holds the address of one of the branch's locals.
    - **A call's places that overlap** (§3.1): where the call is given each of the two, ``` `e.list` is given here, for `xs` ```, or for one a bound function holds, ``` `f`, which holds `e.list`, is given here, for `f` ```. Where the callee has a body and the error says what it does with each place, the notes are at those two accesses in the callee instead: ``` `f` changes `e.list.len` here, through `xs` ```, with ``(the access is in `push`)`` after it if the access is in a function that one calls.
    - **The order of a call's fields** (§3, rule 10): where each of the two fields reads or changes the place, ``` `n` reads `s.n` here ``` and ``` `z` changes `s.n` here ```, in the order the message names them.
    - **A place inside a `match &p`'s arms that overlaps `p`** (§8, Match): `the match's scrutinee is here`.
    - **A name declared twice** in one scope: ``` the earlier `x` is declared here ```; and **an integer pattern that an earlier one covers** (§8, Match on integers): `the earlier pattern is here`.
9. **`--json`** on `check`, `run`, `exe` and `test`, before PATH or after it but before any `--`, writes the diagnostics as JSON instead: one object on a line of standard error for each, with what the text form has, and a summary after them.

    ```text
    {"type":"diagnostic","severity":"error","file":"lib/a.ctx","line":4,"column":5,"end_line":4,"end_column":14,"message":"returned value holds the address of local `v`","notes":[{"file":"lib/a.ctx","line":3,"column":5,"end_line":3,"end_column":19,"message":"`v` is declared here"}],"fixes":[]}
    {"type":"summary","errors":1,"more":false,"waiting":["order","tasks","consts"]}
    ```

    - **A diagnostic** has `type`, `"diagnostic"`; `severity`, `"error"`, the one there is; `file`, `line` and `column`, the text form's PATH, LINE and COL; `end_line` and `end_column`, where what it is about ends, the place after its last character, so that the two are equal to `line` and `column` for an error at a point; `message`; `notes`, an array, empty for most, of objects with `file`, `line`, `column`, `end_line`, `end_column` and `message`; and `fixes`, an array, empty for most, of what to write (rule 12).
    - **The summary** has `type`, `"summary"`; `errors`, how many diagnostics came before it; `more`, whether there were more than the 100 that `run`, `exe` and `test` show (rule 5); and `waiting`, which of rule 5's three checks didn't run, as `"order"`, `"tasks"` and `"consts"`. `check`'s last line (rule 6) isn't written: the summary has what it says.
    - **The fields keep their names and meanings,** and a later version may add others: a reader takes the fields it knows. There is no code for each kind of error: the message is the one name a kind has, the tests compare it whole (tests/README.md), and a number beside it would be a second name to keep true at each of the checker's five hundred errors.
    - **The strings** are JSON's: `"`, `\` and the characters below U+0020 are escaped, and a byte that is not UTF-8, as a file's name may have, is written as `\ufffd`. Everything else is as the text form has it.
    - **Standard error, not standard output,** in both forms: the diagnostics are in one place whichever form they have, and standard output stays the program's under `run` and the tests' results under `test`.
10. **What is not a record.** A line of standard error that doesn't start with `{` is the driver's own failure, as text: a file it can't read, a directory without `.ctx` files, a build program that fails, the C compiler's output. No summary follows one: a run that ends without a summary failed for a reason its lines give. An error of the driver's that is at a place in build.ctx (§19, rule 12) is a diagnostic like any other.
11. **Under `run --json`,** a compile error and the program's own output are told apart by the summary: the compiler writes its diagnostics and the summary, and only if `errors` is 0 starts the program, whose standard error is everything after that line; a panic is the program's, lines of text there, its own and its call path's (§15, Call paths, rule 10), not a diagnostic. With errors the exit code is 1 and nothing after the summary. `test --json` is the same, with the tests' results on standard output (§20, rule 15).
12. **Fixes.** An error whose message says what to write carries that as a **fix**: edits, each a place in a file and the text that goes there, with a message that says what they do. In JSON they are the diagnostic's `fixes`; the text form has no line for them, since the message says the same, and `check`'s last line counts those that `--fix` would apply.

    ```text
    "fixes":[{"safe":true,"message":"discard the result","edits":[{"file":"a.ctx","line":6,"column":5,"end_line":6,"end_column":5,"text":"_ = "}]}]
    ```

    - **An edit** has `file`, `line`, `column`, `end_line` and `end_column`, as a diagnostic's, and `text`: what is from the start up to the end becomes `text`. Start and end equal is an insertion there, and an empty `text` a deletion. The edits of one fix go together, none without the others, and their places are in the file as it was checked.
    - **A fix is safe** (`"safe":true`) if it is what the message says to write and writing it decides nothing that the message leaves open. These are: a pun that names no field, where one field can be meant (`m = &movie`); `_ = ` before a call's result or an `iferr`'s value that is unused; `@as(T, X)` for a const computed by running code where another integer type is wanted; `..` at the end of a call that lacks fields which locals of those names and types supply (§3, rule 7), and of a literal that lacks only fields with defaults (§7); the element of a pointer, `(q + i).*` (§12, Pointers); `@clamp`'s two literal bounds the other way round; no braces after an enum value, a variant without a payload or an error without one; the variant alone after `is`; `&` before the optional of an `if let &x`; `.*` after the pointer a `match` goes through; no `&` before a pointer that is what a `mut` field takes (rule 7); a `,` between fields written without one (rule 7); `{} ` for a function without its context; no braces after a capability without fields; for a `for`, `0..n` for a number or for `range(n)`, `lo..hi` for `range(lo, hi)`, `lo..hi + 1` for `lo..=hi`, and no `&` before a range's name; and each form of another language of rule 7 but a call or a literal with parentheses and an enum without its type: `not`, `and`, `or`, `x = x + n` (with parentheses around an operand that has an operator), `x = x + 1`, `@as(T, x)`, the `if`, `.`, `.*`, braces for a function's fields, `let mut`, `while true`, `s.len`, `x = 1` for `x: 1`, `::` for `.`, and `u8`, `f64`, `bool` and `usize` for `byte`, `double`, `boolean` and `size_t`.
    - **A suggestion** (`"safe":false`) is one of several ways to go on, each a fix of its own in `fixes`, or a guess: the two places for the parentheses of a handler beside a comparison (§11, Expressions, rule 7); each field a pun could name, where there are several; either operand converted to the other's type, for operands of two types; `for x at i` for `for i, x`, which takes the first name for the index; another name for a keyword used as one, which every use needs too; the braces of a call or a literal written with parentheses, which take the arguments for the fields in their order; for an enum without its type, `: u8` or a union; and for `string`, `str`, `String`, `int`, `uint`, `long`, `short`, `char` and `float`, the ctxlang type of the size most like it. A person or a model picks; `--fix` applies none.
    - Most errors have neither: what would mend them isn't known from the error. `"fixes":[]`.
13. **`ctxc check --fix PATH`** applies the safe fixes to the files and checks again, until a check finds none to apply, or ten checks are done; then it reports what the last check found, as `check` does, and exits with 0 only if that is nothing.
    - **Each fix is said** on standard error as it is made: `PATH:LINE:COL: fixed: MESSAGE` at its first edit, then the lines it changes, as they were after `- ` and as they are after `+ `. With `--json` it is a record, `{"type":"fix","applied":true,"message":"...","edits":[...]}`, the edits as in rule 12.
    - **Only the program's own files are written:** those of its directories. A fix in one of std's files, or in a file its build program generates (§19, rule 13), which the next build writes again, is not made, and is said after the last check: `PATH:LINE:COL: not fixed: MESSAGE: the file is std's or one the build program generates, not the program's own` (`"applied":false`, with `reason`). So is no fix in a build program's own files: its errors stop `check` before the executables are looked at (rule 3).
    - **Edits that meet aren't made together.** A fix is applied whole or not at all, and not if one of its edits overlaps one already taken from the same check, or inserts where that one inserts: it waits for the next check, which reads the file as the first left it. That is why `--fix` checks more than once.
    - **Nothing else in a file changes.** Every byte outside the edits stays: the line ends as they are, CRLF or LF, a missing line end at the file's end, tabs. A line break in an edit's text is written as the file's first one is. A file is written once for each check, through a file beside it that is renamed into place.
    - **A file that isn't what was checked isn't written:** if its size, or the bytes an edit replaces, are no longer what the compiler read, `PATH: changed since it was checked: not fixed`.
    - **`--fix --dry-run`** says the fixes of one check as `would fix`, with the same lines (`"applied":false`, `"reason":"a dry run"`), writes nothing, and reports that check's errors. `--dry-run` without `--fix` is a wrong command.
