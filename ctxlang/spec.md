# ctxlang: spec draft

Examples: [examples/list.ctx](examples/list.ctx) (lists, allocators, bound functions), [examples/wordcount.ctx](examples/wordcount.ctx) (files, arguments, maps), [examples/json](examples/json) (a JSON parser and printer, as a program of several files: `python tools/ctxc.py examples/json --run FILE`), [examples/glfw](examples/glfw) (a build program, §19, and a binding of a C library, §18: `python tools/ctxc.py examples/glfw --run`), [examples/sdl](examples/sdl) (SDL2's events through an extern union, §12).

## 1. Top level

1. A program is a sequence of declarations: `fn`, `extern fn` (§18), `struct`, `union`, `enum`, `type`, `const`, `capability` (§15), `error` (§8, Errors), `namespace`. Any declaration may have attributes (§18).
2. There is no mutable state at top level. Top-level names may be referenced from anywhere.
3. All effects (IO, memory, OS) reach a function only through its context.
4. Source files are UTF-8. Names are ASCII: a letter or `_`, then letters, digits and `_`, and not a keyword: `fn` `struct` `union` `enum` `type` `const` `namespace` `let` `mut` `if` `else` `while` `break` `continue` `match` `return` `defer` `and` `or` `not` `true` `false` `null` `extern` `capability` `ifnull` `iferr` `try` `is`. Other characters may appear only in comments, which are `// to the end of the line` and `/* ... */` (not nested). String and character literals are ASCII too (§11 Literals).

## 2. Functions and contexts

```
fn name(Generics) { field: T, mut field: T, ... } -> R { body }
```

1. The `{ ... }` after the name is the **context**. It is the function's only input.
2. A context field is read-only unless marked `mut`.
3. A function can't assign to a read-only field or any field or element of it. Memory reached through a pointer inside it is not part of it (§12, Pointers).
4. `-> R` may be omitted. The function then returns no value.
5. Two fields in one context can't share a name.
6. A `mut x: T` field holds a `*mut T`. Inside the function, `x` is the place of type `T` it points to, and `&x` gives the `*mut T`.

## 3. Calls

```
f{ a = expr, b = &place, c, &d, .. }
```

1. A call is an expression of function type followed by `{ ... }`.
2. Every context field of the callee must be supplied exactly once. Order doesn't matter.
3. A read-only field of type `T` takes an expression of type `T`.
4. A `mut` field of type `T` takes an expression of type `*mut T`. If the argument has the form `&p`, `p` must be a mutable place and §3.1 applies. Any other `*mut T` expression is accepted unchecked. For a capability `T`, a pointer to one that includes it is accepted too (§15, rule 10).
5. Places and mutable places are defined in §11.
6. Punning: `c` means `c = c`, and `&d` means `d = &d`.
7. Forwarding: a trailing `..` supplies each remaining field `F` from the local or context field named `F`. Namespace and top-level names are not considered. It supplies `F = F` for a read-only field and `F = &F` for a `mut` field. It is an error if `F` isn't in scope, or if `F` is `mut` and the name isn't a mutable place.
8. `..`, when present, must be the last item.
9. A call's result may be discarded.

### 3.1 Exclusivity

1. Only places (§11) that don't go through a deref are checked. Their root is a local, context field or match binding.
2. Two places **overlap** if one's steps are a prefix of the other's, with the same root. Any two `[index]` steps count as equal.
3. A call's **mut references** are each place `p` supplied as `&p` to a `mut` field, and each place `p` held as `&p` by a bound-function argument.
   - A bind holds every place it takes as `&p`, plus every place held by its `&fn` arguments.
   - A `&fn` local holds every place held by any bind assigned to it.
   - A `&fn` context field holds no checked places.
4. Two mut references of one call must not overlap. A violation is a compile error.
5. If a read-only field's argument is a place that overlaps a mut reference of the same call, it is passed by copy.
6. Pointers that don't come from `&p` in the call itself are not checked, and neither are places that go through a deref, a capability's static among them (§15, rule 13).

## 4. Binding

```
f{ a = expr, _ }
```

1. A trailing `_` makes the call a **bind**. It produces a function value whose context is the callee's context minus the supplied fields.
2. `_` and `..` can't appear in the same call.
3. The result is a **bound function** of type `&fn{C} -> R` (see §6).
4. A read-only argument is evaluated and copied when the bind executes. A `mut` argument stores its pointer. §3.1 applies to a bind as to a call.

## 5. Function types

```
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

`Cs` may have fields that `Cg` lacks. Those fields are dropped when the value is called. A result of the second kind in rule 1 is **widened**: when `g` fails, the value's error is the same error, with its payload, in the numbering of `Rs`'s set: any error's, or the declared set's (§8, Errors, rule 13). Both happen in one step: calling the converted value calls `g` once with the fields it takes, and widens what it returns. It is implicit wherever widening is (§11, Widening, rule 1), the `T` of an implicit `T` to `?T` conversion included.

```
fn number { s: []u8 } -> !u64 { ... }            // fails with number's set, inferred
fn word { s: []u8 } -> !u64 { ... }

// Before: a function with an inferred set wasn't a value, so a table of parsers was a chain
// of calls.
fn parse_with { kind: u8, s: []u8 } -> !u64 {
    if kind == 0 { return number{ s } }
    return word{ s }
}

// Now: each converts to the table's type, whose `!T` may fail with any error.
fn parse_with { table: []fn{ s: []u8 } -> !u64, kind: u8, s: []u8 } -> !u64 {
    return table[@as(usize, kind)]{ s }
}
let parsers: [2]fn{ s: []u8 } -> !u64 = [number, word]
match parse_with{ table = parsers[..], kind = 0, s } {
    ok{ value } => { ... }
    err{ error } => {
        match error {
            parse::bad_digit{ at } => { ... }     // number's error, with its payload
            else => { ... }                       // any error: `else` is needed (§8, Errors, rule 10)
        }
    }
}
```

## 6. Bound functions

1. `&fn{C} -> R` may only be the type of a local or of a read-only context field. It can't be a return type, a struct field type, a union payload type, an array element type, the `T` of `?T` or `*T`, or the type of a `mut` context field. A value whose inferred type holds one is an error as well: `&f`, `[f]`, or an `if` whose branches give `f` and `null`.
2. A bound function can't be assigned to a local declared in a scope outside that of any place it holds (§3.1.3, including places held through nested binds).
3. A bound function may be stored in a local and passed as a call argument. Its capture record lives until the invocation that creates it returns, after its deferred statements, on both normal returns and `try` returns. A later execution of the same bind never changes what an earlier one's value, if it can still be called, calls with: in a loop, each keeps what it captured. Whether two executions share memory can't be seen, so the compiler reuses a record's memory where no earlier value can still be called. A never-returning invocation that keeps records it can still call keeps their memory; records are not reclaimed at their last use.
4. Code that only calls a function value should take `&fn`, which accepts both kinds. Code that stores one must take `fn`, which rejects bound functions.

## 7. Structs

```
struct Name(Generics) { field: T, ... }
Name{ field = expr, field, ... }
```

1. A struct literal supplies every field exactly once. Punning works as in calls.
2. A field may have type `fn{C} -> R` but not `&fn{C} -> R` (§6).

## 8. Unions

```
union Name(Generics) {
    variant{ field: T, ... },
    variant,
}
```

1. Unions are tagged. A value holds exactly one variant.
2. A variant has a payload (a list of named fields) or no payload.
3. Construction: `Name::variant{ field = expr, ... }` or `Name::variant`. Every payload field must be supplied exactly once. Punning works as in calls.

### Match

```
match e {
    variant{ f, g }           => { ... }
    variant                   => { ... }
    a{ x = n } | b{ y = n }   => { ... }
    else                      => { ... }
}
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

### Match on integers

```
match op {
    0 => { ... }
    OP_ADD | OP_SUB => { ... }          // folded consts (§14)
    gl::TRIANGLES => { ... }
    'a'..='z' | '_' => { ... }          // a range includes both ends
    -8..=-1 => { ... }
    else => { ... }
}
if c is '0'..='9' { ... }
```

1. A scrutinee of an integer type (`i8`..`i64`, `u8`..`u64`, `usize`) is matched by value. Its patterns are integer literals (a character literal is one), with a `-` or not; names of consts, with their path, whose values are folded (§14, rule 1); and ranges `lo..=hi` of these, which include `lo` and `hi`. `lo..hi` is a syntax error.
2. Each value must convert to the scrutinee's type as an argument would (§11, Widening and Literals): `300` doesn't fit a `u8`, and an `i32` const doesn't convert to one.
3. No value may be matched by two patterns, in one arm or two, and a range's `lo` can't be above its `hi`.
4. `else` is required, even if the patterns cover every value. Patterns have no bindings.
5. A pointer to an integer is an error: match on `p.*`. Let-else doesn't apply to integers.
6. `e is P | Q` tests an integer the same way (§8, Is), and binds nothing.

### Optional

1. `?T` is a built-in union with variants `null` and `some{ value: T }`.
2. `null` is a value of every `?T`. An expression of type `T` converts implicitly to `?T` as `some{ value = expr }`.
3. Narrowing: where an `x` of type `?T` is known not to be null, it has type `T`. `x` must be a `let` local or a read-only context field, or a path of struct fields from one, such as `v.a.b` (not through a pointer, `.*` or an index). To narrow a mutable one, copy it first (`let y = x`) or `match` on it.
4. A condition narrows some `x`s when it is true and some when it is false:
   - `x != null` narrows `x` when true; `x == null` narrows `x` when false.
   - `x is P` narrows `x` when true, unless `P` lists `null`: then it narrows `x` when false, as `x == null` does (§8, Is).
   - `not c` swaps what `c` narrows when true and when false.
   - `a and b` narrows, when true, what `a` or `b` narrows when true; when false, what both narrow when false.
   - `a or b` narrows, when true, what both narrow when true; when false, what `a` or `b` narrows when false.
   - Any other condition narrows nothing.
5. Where narrowing holds:
   - In `a and b`, what `a` narrows when true holds in `b`. In `a or b`, what `a` narrows when false holds in `b`.
   - In `if c { B1 } else { B2 }`, what `c` narrows when true holds in `B1`, and when false in `B2`. In `while c { B }`, what `c` narrows when true holds in `B`.
   - After an `if` statement: if one branch always leaves (it ends a path, §11.7, 8, 9), the other branch's narrowing holds from after the `if` to the end of the enclosing block. Without an `else`, that is what `c` narrows when false, if the `{ }` leaves. A `let x` in that same block is an error if `x` was declared there, and shadows it otherwise.
6. Representation: `?*T` and `?*mut T` are a pointer, the size of one, with `null` the address 0. A pointer is never null (§12), so no tag is needed, and the layout is C's nullable pointer, which is what lets one cross into C (§18). So are `?extern fn{C} -> R` (§12) and `?c::String` (§18), whose pointer is never null either. Every other `?T`, `??*T` included, holds a tag and its payload.
7. `e ifnull x`, for `e` of type `?T`, is `e`'s value if it has one, and otherwise `x`, which is evaluated only then. `x` is an expression, or a block that gives a value or leaves, as a branch of an `if` expression does (§11, If and match expressions): `f{} ifnull { return 1 }`. It is the expression `match e { some{ value } => { value } null => { x } }`, and its type is that match's: `T` when `x` converts to `T`, and `?T` when `x` is a `?T` (or `null`). `ifnull` groups right to left, so `a ifnull b ifnull 0` tries `a`, then `b`. It is an error if `e` isn't an optional; a narrowed `x` (rule 3) isn't one.

```
let d = hex_digit{ c }            // ?u32
if d == null { return null }
v = v * 16 + d                    // d: u32

if o == null or o.name == null { return }
print{ s = o.name }               // o: Obj, o.name: utf8::String

let n = utf8::parse_i64{ s } ifnull 0              // i64
let e = map::get{ m, key } ifnull { return null }   // leaves when the key is missing
```

### Is

```
if r is local{ var } { use{ var } }             // r: ?Ref, for a union Ref
if not (r is local{ var }) { return }           // var is bound from here to the end of the block
if r is constant | variant | enumval { ... }
if c is some{ to } | slice{ to } { use{ to } }  // both bind `to`, of one type
if r is local { take{ r } }                     // r: Ref here
let found = map::get{ m, key } is field         // ?Kind for an enum Kind: null doesn't match
```

1. `e is P` is a `bool`: true when `e` holds `P`'s variant. `P` is a pattern as in a match arm (§8, Match), its variant named alone, or several separated by `|`: then it is true for any of them, and each must bind the same names, each with the same type, as an arm's patterns do (§8, Match, rule 3). A binding is read-only: `&f` is an error.
2. `e` is a union, an enum, a `?T` or an integer (§8, Match on integers). A pointer is an error, and so is a `!T` or an error: use `match`.
3. On a `?U` for a union or enum `U`, a pattern may name a variant of `U`, which null doesn't match. `null` and `some` still name the optional's own variants. `match` doesn't do this: it lists exactly its scrutinee's variants.
4. Its bindings are bound where the test is known true. `e is P` binds them when true, and `not`, `and` and `or` combine what conditions bind as they combine what they narrow (§8, Optional, rule 4). A name that would be bound twice, as in `a is x{ v } and b is y{ v }`, isn't bound, and neither is one that only one side of an `or` binds.
5. They are in scope where narrowing would hold (§8, Optional, rule 5): in `b` of `a and b`, in the first branch of `if c` and the body of `while c`, and after an `if` whose branch leaves when `c` is false. After an `if`, they are declared in the enclosing block as a let-else's bindings are (§11, Let-else): a later `let` of the same name in that block is an error.
6. `x is P`, for an `x` of type `?T` that can narrow (§8, Optional, rule 3), narrows `x` to `T` where it is known true, for a `P` that doesn't list `null`: `if r is local { take{ r } }`. A `P` that lists `null`, as `x is null` does, narrows `x` where the test is known false, as `x == null` does. This is the narrowing of §8, Optional, so it combines with `and`, `or` and `not` and holds where any narrowing would. A `let mut` local doesn't narrow.
7. `is` binds at the level of `==` and doesn't chain with comparisons (§11, Expressions). `not e is P` is `not (e is P)`, and `a is x and b is y` needs no parentheses.

### Errors

```
namespace parse {
    error empty
    error bad_digit{ at: usize }                 // an error with a payload
}

fn number { s: []u8 } -> !u64 {                  // a u64, or one of the errors its body returns
    if s.len == 0 { return parse::empty }
    ...
    return n
}

fn pair { a: []u8, b: []u8 } -> !u64 {
    let x = try number{ s = a }                  // number's error is returned: pair's set gains number's
    let y = number{ s = b } iferr 0              // or a default
    return x + y
}

match pair{ a, b } {
    ok{ value }  => { ... }
    err{ error } => {
        report{ error }                          // code every error shares, once
        match error {                            // then by kind, exhaustive over pair's set
            parse::empty        => { ... }
            parse::bad_digit{ at } => { ... }
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
7. `try e`, for `e` of type `!T` in a function that returns `!U`: `e`'s value, or, if `e` is an error, `return e` (deferred bodies run first). The function's set gains `e`'s errors. It is a prefix operator, at the level of `not`: `try f{}.x` takes `.x` of `f{}`'s value. `try` is an error in a `defer`, and as a statement its operand must be a call. `try! e` is `e`'s value, or, if `e` is an error, a panic, as `@panic` (§13), at the `try!` whose reason names the error without its payload: for an error the function can't handle, such as running out of memory where that is fatal. It needs no `!U` result, adds nothing to the function's set, and is allowed in a `defer`; as a statement its operand must be a call, as with `try`.
8. `e iferr x`, for `e` of type `!T`, is `e`'s value if it isn't an error, and otherwise `x`, as `ifnull` is for `?T` (§8, Optional, rule 7): `x` is an expression, or a block that gives a value or leaves. `e iferr err{ error } { ... }` binds the error in the block, as `let ... else` does. For a bare `!` it has no value, and is a statement: `close{ &fs, file } iferr { return 1 }`. It groups right to left with `ifnull`.
9. A `match` on a `!T` has the arms `ok{ value }` (`ok` for a bare `!`) and `err{ error }`, where `error` has the `!T`'s error type. `let ok{ value } = e else err{ error } { ... }` takes one apart (§11, Let-else). The arms may instead list errors next to `ok`: then `ok` must be listed, and a last `err{ error }`, or `else`, takes the errors not listed. A `match` on an error lists errors, with `else` for the rest. An arm doesn't mix `ok` or `err` with errors.
10. A listed error must be one the value can be, and without `else` or `err` every one it can be must be listed: adding an error to a function breaks the matches that listed all of its errors. With `else` or `err`, at least one must be left for it. These are checked once the sets are inferred. A value of `error`, or of a function type's `!T` that declares no set, may be any error of the program, so a match on one needs `else` or `err` (rule 15).
11. An error type or a `!T` isn't a C type (§18) and can't be held by a const (§14). Neither has a zero value. `match` doesn't go through a pointer to one.
12. A function whose result's set is inferred, or declared, is a value of a function type whose `!T`, of the same `T`, may be any error (§5), or fails with a declared set that holds its errors (rule 14): its error is widened into that set's numbering. A bind of it (§4), and a generic one's instance, convert the same way. A value called through that type fails with its set: any error, so a match on its result needs `else` or `err` (rule 10) and lists the function's errors to get them back with their payloads, or the declared set. Any error takes every set, so that conversion is allowed while the sets are still inferred, in a function that converts itself included; one into a declared set is checked once they are. A call through the value is a call (§14, Escape check): its error may hold what its read-only arguments are derived from, if any error of the program has a payload that holds a pointer. No written type names a function's inferred set: a local inferred from the function (`let g = f`) has it, as `f{}`'s result does, and takes no other function's (rule 6). Neither changes for an `extern fn`, which can't return a `!T` (§18), nor for consts, which hold no function value (§14).
13. Representation: `!T` is a tagged union of `ok{ value: T }` and `err{ error: E }`. An error type is a tagged union of its set's errors, in the order they are declared in the program, sized for the largest payload; passing an error into a larger set renumbers it. Two error types with the same errors, both open or both not, are the same type. A function value widened by §5 is a thunk the compiler writes, which calls the function and renumbers its error, copying the payload: for a named function, or a bind of one, it calls the function directly and is no more a record than the function or the bind was; any other value it holds in a record of its own, made when the value converts. A function whose set is already every error needs none.
14. `E!T`, or `E!` without a value, is a `!T` whose errors are set E's: `error(A, B, ...)`, whose errors are those of each of A, B, ..., each an error or a set; an alias of one (`type ParseError = error(empty, bad_digit)`); one error alone (`parse::empty!u64`); or `error`, any error. A function's result written so **declares** its set: its body may fail only with E's errors, which is checked once the sets are inferred, and every caller sees E, whatever the body returns, so a match on its result lists E's errors (rule 10). E may hold errors the body never returns: a declared set is what the function may fail with, a contract that holds however its body changes, and that several functions can share, as std's platform layers do (§17). A declared set converts to a larger one or to any error, as an inferred one does, and an inferred one joins a declared one only if each of its errors is in it. A function type may declare one too, `fn{ ... } -> E!T`: a function value converts to it if its errors are in E (an inferred set's checked once it is), its error renumbered as rule 12's are, and a call through it fails with E.
15. `error(A, B, ..)`, with `..` last, is an **open** set: it may gain errors, as one whose errors come from the platform does (§17). A match on an open set, or on a set it joined, needs `else` or `err` even when it lists every error, and that arm isn't unreachable. A set that holds an open one, `error(Open, c)`, is open, and so is a function's inferred set once an open set joins it: through `try`, a return or a writer (§13, Formatting). An open set joins only an open set, or any error: a closed set promises its errors are all there are, which an open one can't.

## 9. Generics

1. Generic parameters are types, listed in `( )` directly after a declaration's name.
2. `( )` after a name or `::` path, on the same line, is generic application: `list::new(i32)` and `list::new (i32)` mean the same. Everywhere else, `( )` groups an expression. This is unambiguous because calls use `{ }` and nothing else can follow a name with `(`. Builtins are the exception (§13).
3. At a call, struct literal or union construction, explicit arguments bind parameters left to right. The remaining parameters are inferred from the supplied fields or the expected type. A parameter that can't be inferred is an error.
4. In a literal, a generic struct or union may be named without arguments (`Slice{ ... }`), and then every parameter is inferred.

## 10. Namespaces

```
namespace name { declarations }
name::item
```

1. A namespace holds only top-level declaration kinds (§1). Namespaces may nest.
2. Inside a namespace, its own items are referenced unqualified.
3. `::` resolves namespace members and union and enum variants. `.` resolves struct fields.
4. Two `namespace` declarations of one name in one scope, in one file or in several, declare one namespace: each adds its declarations to it, and inside either, the other's items are referenced unqualified. A name still can't be declared twice in it, from one file or two. A namespace nested in one of them joins the one of its name nested in the other, as `gff::inner` does below. std's namespaces and the program's are in different scopes (§17), so a program's `list` never joins std's: it shadows it.

```
// gff/read.ctx
namespace gff {
    fn read { bytes: []u8 } -> !Gff { ... check{ bytes } ... }
    namespace inner { fn base {} -> i64 { return 1 } }
}

// gff/write.ctx
namespace gff {
    fn check { bytes: []u8 } -> ! { ... }      // gff::check, which read calls unqualified
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

## 11. Statements and control flow

```
let x = e      let mut x = e      let x: T = e      let x: T      let mut x: T
let variant{ f, g = y } = e else { }      let ok{ value } = e else err{ error } { }
x = e
_ = e
if e { } else if e { } else { }
while e { }
label: while e { }
break      break label
continue   continue label
match e { ... }
return e
return
defer f{ ... }      defer x = e      defer _ = e      defer { }
f{ ... }
```

1. Conditions and match scrutinees need no parentheses: the block's `{` ends them. Parentheses are allowed, as around any expression.
2. `{` after `else` or `=>` begins a block. In a condition or scrutinee, outside any brackets, a `{` after an expression begins a call or literal only if the token after its matching `}` is on the same line and isn't `else`, `;`, `,`, `}`, `)` or `]`. Otherwise it begins the block: in `if ok{ r } { }` the first `{` is a call and the second the block, and in `if done { }` the `{` is the block. So a condition that goes on to the next line must break after an operator, not right after a call's `}`. Everywhere else, `{` after an expression begins a call or literal. In a let-else, `{` after the `else`'s variant holds its pattern if another `{` follows its `}`, and is the block otherwise.
3. Statements are separated by newlines or `;`. A postfix `{`, `[` or `(` must be on the same line as the expression before it.
4. Every block is a scope. A `let` is visible from its declaration to the end of its block.
5. In `x = e`, `x` must be a mutable place.
6. An expression statement must be a call or a builtin call that returns nothing, `try` of such a call, or `iferr` on a bare `!` (§8, Errors). A call that returns a value is an error as a statement, a `!T` or `!` included: use the value, or discard it explicitly with `_ = e`. `_ = e` evaluates any expression `e` that has a value, and drops it; `_` is not a name and can't be declared. The exception is the last statement of a branch of an `if` or `match` expression, which gives the branch its value (below).
7. `return` without a value is only allowed in a function with no `-> R`. In a function with `-> R`, every path must end in `return e` or `@panic()`.
8. `break` leaves the innermost enclosing `while`. `continue` skips the rest of its body and goes to its next condition check. Both are errors outside a loop, and both end a path.
9. `while true` without a `break` that leaves it ends a path, like `return`.
10. Labels: `name:` before a `while`, on the same line or the line above, labels it. Only a `while` can be labeled. `break name` and `continue name` act on the enclosing loop labeled `name` instead of the innermost one, leaving any loops in between. It is an error if no enclosing loop has that label, or if a loop is labeled with a name an enclosing loop already uses. A jump in a `defer` body sees only the loops inside that body (§11, Defer). Deferred bodies run for every block the jump leaves, innermost first.

```
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

### Let-else

```
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

### Defer

```
let mut xs = list::new(i32){ realloc = arena::alloc, &heap }
defer list::free{ list = &xs }
```

1. `defer` takes a call, an assignment, a discard (`_ = e`) or a block. Its body runs when the enclosing block exits: at its end, or through `return`, `break`, `continue`, or a branch of an `if` or `match` expression leaving (§11, If and match expressions).
2. A block's deferred bodies run in reverse order of their `defer` statements. Only `defer` statements that were reached run.
3. The body is evaluated when it runs, not at the `defer`: `defer say{ n = i }` sees the value `i` has at exit. A `return e` evaluates `e` before deferred bodies run.
4. A `defer` inside a loop body runs at the end of each iteration that reached it.
5. Deferred bodies don't run when the program stops through `@panic()`.
6. The body is checked where it appears. It can read only variables that are assigned there (§11, Initialization), and it can't assign a `let x: T` declared outside it.
7. The body can't leave: `return` is an error in it, and `break` and `continue` in it must be inside a loop that is also in it.

### If and match expressions

```
let sign = if n < 0 { -1 } else if n == 0 { 0 } else { 1 }
let v = match parse{ s } {
    ok{ value }  => { value }
    err{ error } => { return error }
}
```

1. `if` and `match` are statements at the start of a statement, and expressions everywhere else.
2. An `if` expression must have an `else`.
3. Each branch is a block whose last statement is an expression: the branch's value. `{ let y = f{}; y + 1 }` has the value `y + 1`.
4. Instead of ending in a value, a branch may leave: it ends a path (§11.7, 8, 9) through `return`, `break`, `continue` or `@panic()`. At least one branch must produce a value.
5. A branch whose last statement is an `if` with an `else`, or a `match`, takes that statement's value, unless every one of its branches leaves.
6. Type: if the expression has an expected type (§11, Widening, rule 1) that every branch value converts to, that type. Otherwise the first branch type that every other branch value converts to, where `null` among the branches makes it `?T`. It is an error if there is none.
7. Narrowing (§8, Optional) applies in the branches as in an `if` statement.
8. A branch value must not hold the address of, or a bound function holding, a local declared in that branch (§6, §14).
9. An `if` or `match` expression takes no postfix operators. To apply one, put the expression in parentheses.

### Expressions

Precedence, tightest first:

| Level | Operators | Notes |
|---|---|---|
| postfix | `.f` `.*` `[i]` `[lo..hi]` `{ ... }` `::x` `(G)` | left to right |
| prefix | `&` `-` `not` `try` | `try`: §8, Errors; `not e is P` is `not (e is P)` |
| multiplicative | `*` `/` `%` | left to right |
| additive | `+` `-` | left to right |
| shift | `<<` `>>` | left to right |
| bitwise and | `&` | left to right |
| bitwise xor | `^` | left to right |
| bitwise or | `\|` | left to right |
| ifnull | `ifnull` `iferr` | right to left; the right side may be a block (§8, Optional, Errors) |
| comparison | `==` `!=` `<` `<=` `>` `>=` `is` | don't chain: `a < b < c` is an error; `is`: §8, Is |
| and | `and` | short-circuit |
| or | `or` | short-circuit |

1. Arithmetic and comparison apply to two operands of the same numeric type, after widening (below). If the operand types differ, the one that widens to the other is converted. If neither widens to the other, it is an error. Use `@as` or `@trunc` (§13).
2. Integer `+ - *` panic on overflow. `/` and `%` panic on a zero divisor. Use `@wrap_*` (§13) for wrapping arithmetic.
3. `&`, `|` and `^` apply to two operands of the same integer type, after widening as in rule 1. They act on the two's complement bits and never panic.
4. `a << n` and `a >> n` shift integer `a` by `n` bits. The result has `a`'s type. `n` may have any integer type and doesn't widen to or from `a`'s. A count below 0, or at or above `a`'s width in bits, panics. `<<` drops the bits shifted out, so it never overflows: `x << 1` wraps where `x * 2` panics. `>>` is arithmetic for signed types (it copies the sign bit) and logical for unsigned ones.
5. `==` and `!=` work on numbers, `bool`, pointers (by address) and two values of one enum (§12, Enums), and on `?T` against `null`. Other types have no built-in equality.
6. `and`, `or` and `not` take and give `bool`. Conditions must be `bool`.

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
3. Wherever rule 1 applies, a `*[N]T` converts implicitly to a `[]T`, and a `*mut [N]T` to a `[]mut T` or `[]T`: the slice of the whole array.
4. Wherever rule 1 applies, a capability converts implicitly to one it includes (§15, rule 10).
5. Nothing else converts implicitly. In particular integers don't widen to floats, `usize` doesn't widen to a signed type, `*T` doesn't convert to `*mut T` nor `[]T` to `[]mut T`, and `?A`, `*A` and `[N]A` don't convert to `?B`, `*B` and `[N]B`. A `mut` field's argument is a `*mut` pointer, so its type must match exactly, except that it may point to a capability that includes the field's (§15, rule 10).
6. `usize` is at least 32 and at most 64 bits wide on every target, which is what makes the `usize` rows lossless.

### Literals

1. An integer literal (`42`) has an integer type that is inferred from every use within the enclosing function body, including uses of locals it initializes. If no use fixes it, it is `i32`.
2. A float literal (`1.5`, `2e3`) is inferred the same way among float types, and defaults to `f64`.
3. `true` and `false` are the `bool` values. `null` is described in §8.
4. `[a, b, c]` is a `[3]T` array. Every element has type `T`.
5. `[x; N]` is a `[N]T` array with every element a copy of `x`. `N` is a compile-time integer constant (§14).
6. A string literal `"..."` holds `N` bytes. Its type depends on the type expected where it appears (also inside `?`):
   - `strlit` (§12): the literal itself. Its `bytes` are static and read-only, and live for the whole program.
   - `[]u8`: a **view** of those bytes. `[]mut u8` is an error.
   - a type `T` that a `#convert` fn gives (§18, Literal conversions): that fn's result for the literal, computed while compiling. So std makes a literal a `utf8::String` (§17), whose bytes must be valid UTF-8, or a `c::String` (§18), which can't hold a NUL itself (`\0`), since C would end the string there.
   - anything else, or nothing: a `[N]u8` array value. Like any array it is a value, not a place: bind it to a local to take its address.

   A literal's static bytes are followed by a 0 byte that isn't one of them, the **hidden zero**: `"abc"` as a `[]u8` has `len` 3, and its `ptr[3]` is 0, and `""`'s `ptr[0]` is 0. So a pointer to a literal's bytes is a C string as it is, and nobody writes `"abc\0"` for C.

   In an `if` or `match` expression without an expected type, a branch that is a literal takes the type of another branch that is a `strlit`, a `[]u8` or a type a `#convert` fn gives, or of another literal branch that became one. Otherwise, as in `let msg = match p { a => { "one" } b => { "three" } }`, each literal is an array and the lengths must agree; annotate the `let` to get views.
7. A character literal `'a'` is an integer literal whose value is the character's byte.
8. String and character literals hold ASCII characters only. Escapes, except in a multi-line literal: `\n`, `\t`, `\r`, `\0`, `\\`, `\"`, `\'`, and `\xNN` for any byte.
9. A **multi-line literal** is a string literal written as lines that each start with `\\`, with only spaces and tabs before it on its line. Each line's text is what follows its `\\`, as it is: there are no escapes, and a `\r` that ends the line isn't part of it. The literal's bytes are those texts joined with `\n`, with none after the last; an empty `\\` line at the end adds one. It ends at the first line that doesn't start with `\\`, so a comment can't be among its lines. Otherwise it is a string literal like any other (rule 6), for GLSL or any other text:
   ```
   const MESH_VS: c::String =
       \\#version 410 core
       \\layout(location = 0) in vec3 pos;
       \\void main() { gl_Position = vec4(pos, 1.0); }
   ```

### Places

```
place := root step*
root  := local | context field | match binding | expr.*
step  := .field | [index]
```

1. For a pointer `q`, `q.f` and `q[i]` are places rooted at a deref (§12). So is `s[i]` for a slice `s`.
2. A place **goes through a deref** if its root is `expr.*`.
3. A place is **mutable** if its root is a `let mut` local, a `mut` context field, or a `&f` match binding through a `*mut` (§8), or if it goes through a deref of a `*mut` pointer or a `[]mut` slice: `q.*`, `q.f` or `q[i]` for `q: *mut T`, and `s[i]` for `s: []mut T`.
4. Every other place is read-only.

### Initialization

1. `let x: T` without an initializer: `x` must be assigned exactly once on every path before it is read. An assignment inside a loop is allowed only if no path leads from it back to the loop's next iteration, for example because a `break` follows it.
2. `let mut x: T` without an initializer: if `T` has a zero value, `x` starts as that value. Otherwise `x` must be assigned on every path before it is read.
3. Zero values:

| Type | Zero value |
|---|---|
| integers, floats | `0` |
| `bool` | `false` |
| `?T` | `null` |
| `[N]T` | every element zero, if `T` has a zero value |
| `[]T`, `[]mut T` | the empty slice |
| struct | every field zero, if every field type has a zero value |
| `*T`, `*mut T`, `strlit`, user-defined unions, enums, `fn{C} -> R`, `&fn{C} -> R`, capability types | none |

4. Reading a variable before it is assigned is a compile error. There is no way to declare uninitialized memory.

## 12. Types

| Syntax | Meaning |
|---|---|
| `i8..i64`, `u8..u64`, `usize`, `f32`, `f64`, `bool` | primitives |
| `*T` | read-only pointer to a `T`. Never null. |
| `*mut T` | pointer to a `T` that can be written through. Never null. |
| `[N]T` | fixed array. `N` is a compile-time integer constant (§14). |
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
| `type Name(G) = T` | alias |

### Pointers

1. `&p` is the address of place `p`. It is allowed on any place. Its type is `*mut T` if `p` is a mutable place (§11), and `*T` otherwise.
2. `q.*` is the place that pointer `q` points to.
3. If `q` is a `*S` for a struct `S`, `q.f` means `q.*.f`.
4. `q + n`, with `n: usize`, points `n` elements of `T` after `q`. It has `q`'s type.
5. `q[i]` means `(q + i).*`. It is not bounds-checked.
6. Exception: if `q` is a `*[N]T`, `q[i]` means `q.*[i]` (bounds-checked) and `q.len` means `N`.
7. Pointers aren't tracked. Using a pointer to memory that no longer exists, or outside its allocation, is undefined behaviour.
8. A place reached through a `*T` is read-only: assigning to it, or passing it as `&p` to a `mut` field, is an error. Through a `*mut T` it is mutable (§11).

### Arrays

1. `a[i]` on an array is bounds-checked. An out-of-bounds index panics.
2. `a.len` is `N`, of type `usize`.

### Enums

```
enum Kind: u8 {
    ident,                  // 0
    number,                 // 1
    lbrace = 40,
    rbrace,                 // 41
}
let k = Kind::lbrace
if k == Kind::rbrace { ... }
let i = @as(usize, k)       // 40
```

1. An enum is an integer type with named values. `T`, its base type, is one of `i8`..`i64`, `u8`..`u64` and `usize`. An enum has `T`'s size, alignment and representation.
2. Variants have no payload. The first variant's value is 0, and each later one's is one more than the variant before it, unless `= e` gives it a value. `e` is a compile-time integer constant (§14). It is an error if a value doesn't fit in `T`, or if two variants have the same value.
3. An enum can't have generic parameters.
4. `Name::v` is variant `v`'s value, of type `Name`. An enum converts implicitly to and from no other type (§11, Widening), and has no zero value (§11, Initialization).
5. `==` and `!=` compare two values of the same enum. No other operator applies to enums.
6. `match` takes an enum scrutinee as it takes a union one (§8, Match): arms list variants, the arms must be exhaustive, and patterns have no bindings. So does `is` (§8, Is): `k is lbrace | rbrace`. The scrutinee can't be a pointer to an enum: match on `p.*`. `let` with a pattern (§11, Let-else) doesn't apply to enums.
7. `@as(U, x)` gives the value of enum `x` in integer type `U`, and panics if it doesn't fit. `@as(E, n)` gives the variant of enum `E` whose value is integer `n`, and panics if there is none (§13).
8. A const may hold enum values (§14).

An enum is for a closed set whose values matter: table indexes, file formats, a chosen size. A union whose variants have no payload is for a closed set whose values don't.

### C function pointers

```
type Op = extern fn{ a: i32, b: i32 } -> i32
let some{ value = p } = lib::lookup{ &lib, name = "add\0" } else { return 1 }
let add = @cast(Op, p)                    // the address is a C function of this type
let n = add{ a = 2, b = 3 }
let sub: Op = lib::sub                    // a named extern fn: its C symbol's address
```

1. `extern fn{C} -> R` is a pointer to a C function, as C's `R (*)(...)`: 8 bytes, never null. Its fields are C's parameters in the order they are written, so two such types are the same only if they have the same fields, in the same order, with the same names, types and mutability, and the same result.
2. Its fields and result follow an extern fn's rules (§18): only types with C equivalents, a capability field isn't passed, and a `mut` field passes a pointer.
3. It is called like any function (§3), with every field supplied; it can't be bound (§4). As a capability's field, it can only be called, through the capability (§15, rule 7).
4. A value comes from `@cast(extern fn{C} -> R, p)`, for a pointer `p` (§13), from a named extern fn where that type is expected (the address of its C symbol), or from a named `#c::callback` fn there (a C function that calls it, §18 Callbacks). `@cast(*U, f)` gives the address back.
5. A ctxlang function value (`fn{C} -> R`) doesn't convert to an extern fn type, nor the other way. Only a callback's name does, as rule 4 says.
6. `?extern fn{C} -> R` is a C function pointer that may be `NULL`, as `?*T` is (§8, Optional, rule 6).
7. It holds no addresses of places: as a `fn` value, it may be stored and returned anywhere.

### Untagged unions

```
extern union ClearValue { color: Color, depth_stencil: DepthStencil }

let v = ClearValue{ color = Color{ r = 1.0, g = 0.0, b = 0.0, a = 1.0 } }
let d = v.depth_stencil.depth          // the same bytes, read as another field
```

1. `extern union Name { field: T, ... }` declares C's union: every field starts at offset 0. Its size is its largest field's, rounded up to its largest alignment, and its alignment is its largest field alignment, as in C. It can't have generic parameters.
2. It has no tag, so it can't be matched (§8, Match) or taken apart with `let … else`. A field is read and written as a struct's is (`v.color`, `v.color = c`, `p.color` through a pointer), and is a place as a struct field is (§11). Which field holds a meaningful value is for the program to know, as in C: reading a field other than the one last written reads the same bytes as that field's type.
3. A literal sets exactly one field, and the rest of the bytes are zero.
4. Its zero value is every byte zero, if every field type has a zero value (§11, Initialization).
5. A const can't hold one (§14).
6. Two fields of one extern union are the same place for §3.1: passing `&v.color` and `&v.depth_stencil` to `mut` fields of one call is an error. A value read from a field is derived from whatever the union is (§14).
7. For a union of the language's own, which says which variant it holds, use `union` (§8).

### Slices

A slice is a view of `len` consecutive `T`s that it doesn't own. Slices are built in because they are a shape of memory, like arrays and pointers; what to do with memory (allocating, growing, hashing, text) is left to the standard library.

1. `s.len` is the number of elements, a `usize`. `s.ptr` is a `*T` for a `[]T` and a `*mut T` for a `[]mut T`, pointing to the first element. Neither is a place. The `ptr` of an empty slice is unspecified and must not be dereferenced, except a string literal's view, whose `ptr` points to its hidden zero (§11, Literals).
2. `s[i]` is the element at `i`, bounds-checked: `i >= s.len` panics. It is a place through a deref (§11), mutable only for a `[]mut T`. `s.ptr[i]` is the same element without the check.
3. `s[lo..hi]` is the slice of elements `lo` up to but not including `hi`, of `s`'s type. `lo` defaults to 0 and `hi` to `s.len`, so `s[..]` is `s`. `lo > hi` or `hi > s.len` panics. `lo` and `hi` are `usize`.
4. `a[lo..hi]` on an array place `a` means `(&a)[lo..hi]`, and on a `*[N]T` or `*mut [N]T` it slices the array it points to. The result is `[]mut T` if the place is mutable (§11), `[]T` otherwise.
   - An array const, or an array reached by fields and array indexes from a const, may also be sliced. The result is always `[]T`, backed by immutable static storage (§14), with the same bounds checks. No array is copied to make the view. This does not make the const a place: `&C` and `&C[i]` remain errors.
5. `@slice(p, n)` makes the slice of `n` elements starting at pointer `p` (§13). It isn't checked.
6. Slices have no built-in equality.

## 13. Builtins

1. A name starting with `@` is a compiler builtin. User code can't declare such names.
2. `@name(...)` is always a builtin call, never generic application (§9). The parentheses are required, even with no arguments.
3. Each builtin has the signature below. Type arguments always come before value arguments, so the builtin's name alone says whether each argument is parsed as a type or an expression. Only `@fmt` takes any number of arguments.
4. An unknown builtin, or a call with the wrong number of arguments, is a syntax error.
5. The type argument of `@as`, `@trunc` or `@cast` may be `_`: the type expected where the call appears (§11 Literals), or its payload if that is optional. In `Gl1_1{ clear = @cast(_, p) }` it is the field's type, and in `let n: i32 = @as(_, big)` the local's. It is an error where nothing expects a type, as in `let n = @as(_, big)`. `_` is a type nowhere else.

| Signature | Result | Meaning |
|---|---|---|
| `@size_of(T)` | `usize` | The size of `T` in bytes. |
| `@align_of(T)` | `usize` | The required alignment of `T`. A power of two. |
| `@offset_of(T, f)` | `usize` | The offset in bytes of field `f` of struct `T` from its start, as C's `offsetof`: 0 for an extern union's. `f` is a field's name. |
| `@as(T, x)` | `T` | Converts number `x` to numeric type `T`. Panics if the value isn't representable in `T`. Float to integer rounds toward zero and panics on NaN. Integer to float rounds to nearest. Also converts between an enum and an integer type (§12, Enums). |
| `@trunc(T, x)` | `T` | Converts integer `x` to integer type `T`, keeping the low bits. |
| `@cast(*U, q)`, `@cast(*mut U, q)`, `@cast(extern fn{C} -> R, q)` | the target | Reinterprets `q`, a pointer or a C function pointer (§12), as a pointer or a C function pointer. Unchecked, except that a `*T` can't be cast to a `*mut U`, and `q` can't be optional: check it for `null` first. |
| `@slice(p, n)` | `[]T`, or `[]mut T` for a `*mut T` | The slice of `n: usize` elements starting at pointer `p: *T`. Unchecked. |
| `@addr(q)` | `usize` | The address of pointer `q` as an integer. |
| `@wrap_add(a, b)`, `@wrap_sub(a, b)`, `@wrap_mul(a, b)` | type of `a` | Integer arithmetic that wraps instead of panicking. `a` and `b` have the same integer type. |
| `@panic()`, `@panic("reason")` | none | Stops the program. Never returns. It ends a path for return and assignment checks. The reason must be a string literal. The program's `#panic` fn reports it with the panic's location (§15, Entry point), so no capability is needed. |
| `@fmt(b, "format", args...)`, `@fmt("format", args...)` | `!`; a writer | Writes text into a sink, now or when called (below). |

### Formatting

```
try @fmt(&b, "{}:{}: error: {}", line, col, msg)                    // write into b now
errorf{ &c, at, msg = @fmt("no variant `{}` in {}", name, kind) }   // a writer, passed on
_ = @fmt(&b, "due {} at {}", date::write_iso{ d, _ }, utf8::write_hex{ n = addr, _ })

fn errorf { mut c: Checker, at: Span, msg: utf8::Fmt(Heap) } {
    let mut b = message{ c }
    try! msg{ &b }                                                  // a writer writes when called
    error{ &c, at, msg = utf8::view{ b } }
}

namespace utf8 {
    #write
    fn push_i64(S) { mut b: Builder(S), n: i64 } -> ! { ... }       // how an i64 goes into a Builder
}
```

1. `@fmt(b, "format", args...)` writes text into the **sink** `b`: any expression of type `*mut B`, for a type `B`, evaluated once. `@fmt("format", args...)`, without a sink, is a **writer**: a bound function (§6) that writes the same text into the sink it is called with. Its type is the type expected where it appears (§11, Literals), which must be a function type with exactly one `mut` field, of type `B`, and a bare `!` result, as std's `utf8::Fmt(S)` is: `&fn{ mut b: Builder(S) } -> !`. Without one, as in `let w = @fmt(...)`, it is an error. A format is always a string literal and a sink never is, so the first argument says which form a call is. `@fmt(b, ...)` writes what `@fmt(...)` would, called on `b` at once, without making a bound function.
2. The format must be a string literal of valid UTF-8. Its text is written as it is, except for holes, `{}`, which take the remaining arguments in order; their numbers must match. `{{` and `}}` stand for `{` and `}`.
3. The arguments are evaluated once, at the `@fmt`, in order. A writer copies them as a bind does (§4), and holds what they hold: the places their bound functions hold (§3.1), and what they are derived from (§14), so it can't outlive any of them. With a sink first, the sink and the places the arguments' bound functions hold are one call's mut references (§3.1): `@fmt(&b, "{}", w{ &b, _ })` is an error.
4. A fn with the attribute `#write` is a **writer** of its value to its sink. Its context is two fields: the sink, `mut`, and the value, read-only. Its result is a bare `!`, or nothing, for a writer that records failure itself. It may be generic, but neither field's type is a bare type parameter, the value isn't a function, and every type parameter appears in a field's type. The compiler declares `write`, as it declares `convert` (§18, Attributes). An `@fmt` sees the writers its code could name, as a literal sees conversions (§18, Literal conversions, rule 4). For each piece it looks at the program's writers first, and at std's only if it sees none of the program's, so a program's writer replaces std's for the same types, as its names shadow std's (§10).
5. Each piece of the format is written to the sink, a `B`, by the writer the `@fmt` sees for `B` and the piece's type:
   - text is a `strlit` (§12), and so is a string literal argument;
   - an argument of type `T` is written by the writer for exactly `T`. There's no widening, since a `u32` widens to both an `i64` and a `u64`, except one: a `[]mut T` with no writer of its own is written by that of `[]T`. The types are those the body settles, after integer literals take their defaults (§11, Literals);
   - a function value whose context is one `mut` field, of type `B`, and that returns a bare `!` is called with the sink. This is how a value is written some other way: `utf8::write_hex{ n, _ }` and `date::write_iso{ d, _ }` bind everything but the sink (§4). An `@fmt` without a sink as an argument is written as part of the outer one;
   - an error (§8, Errors) is written by the compiler: its full name, as a `strlit`, and its payload as `{ field = value, ... }`, each value by the writer for its type, or `_` if there is none: `parse::bad_digit{ at = 3 }`.

   A piece with no writer is an error naming both types; an enum converts to an integer with `@as`, and a `?T` gives a value with `ifnull`. Two writers for the same types, both the program's or both std's, are an error naming both, as two conversions are (§18).
6. The result, of `@fmt(b, ...)` or of calling a writer, is a bare `!` (§8, Errors): `ok` if every piece was written, or the error of the first that failed, after which the sink holds the pieces before it. With a sink first, it fails with the errors of the writers it uses: a set of its own, inferred as a function's is (§8, Errors, rule 5), with an argument that is a function adding its type's declared set, or any error if it declares none. A writer's result is its type's, a function type's `!`, which may hold any error, or `E!`, a declared set that must hold the writers' errors (§8, Errors, rule 14). Like any call's result it must be used (§11.6), and `try @fmt(...)` is a statement as `try` of a call is.
7. `@fmt` is short for the writer calls it stands for, each run only if the one before it succeeded. With a sink first it has no cost beyond them; a writer is a bound function, whose record holds the arguments.

## 14. Memory

1. Static memory holds read-only string literal bytes, with the hidden zero after them (§11 Literals), the immutable backing storage of const array views (§12, Slices), and capabilities' statics (§15, rule 13), the only static memory a program writes, reached only through their capabilities. `const NAME: T = e` declares a constant, whose value is computed while compiling. `e` may be any expression of type `T`, calls included. A const has no context, so it holds no capability (§15), and nothing it runs reaches outside the program. A const is a value, not a place, so `&C` is an error. Slicing an array in a const exposes read-only storage that lives until the program ends. The compiler may duplicate that storage; pointer identity between separately obtained const views is not guaranteed.
   - An `e` made of literals, folded consts, enum values, operators, `@size_of`, `@align_of`, `@offset_of`, and struct, union and array literals of these is **folded** before the bodies are checked. What would panic at run time is an error at the operation.
   - Any other `e`, one that uses a const that isn't folded included, is **run** once every body is checked and the error sets are inferred, the first time its value is needed. What stops it is an error at the const: a panic, with its message and position; too many steps, or too deep a recursion; or calling an extern fn (§18), since none can run while compiling.
   - A const whose value needs its own, directly or through the functions it calls, is an error.
   - The value may hold no pointer, slice or function value, except a `[]u8`, a `strlit` or a `*u8` that points into a string literal's bytes (part of them is fine; a `*u8` is followed by the rest of them and the hidden zero), or a struct over one, such as `utf8::String` or `c::String`. Const array views may be consumed during compile-time evaluation, but cannot themselves be stored in a const's value: the evaluator does not preserve references to their backing storage in its result.
   - An array length (§12) or an enum's value can use only a folded const: they are needed before anything can run.
2. Locals and context fields live on the stack.
3. Memory not on the stack comes from `mem::pages`, which needs the `Mem` capability (§15), or from an allocator function over memory the caller provides. It is accessed only through pointers and slices.
   - Allocators are byte-level: `alloc::Fn(S) = fn{ mut heap: S, mem: Bytes, new: usize, align: usize } -> ?Bytes`. The result must be aligned to `align`.
   - Typed code calls the standard library's `alloc::resize(T, S)`, which passes `count * @size_of(T)` and `@align_of(T)` and casts the result, or `alloc::new(T, S)` for one initialized `T`. Both fail with `alloc::out_of_memory` (§8, Errors) where the allocator returns null, as does everything in std that allocates.
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
   - a direct call, whose result is derived from the read-only parameters that may flow into that output. Success and error outputs have separate summaries: `try` propagates only error origins and yields only success origins. A fresh copy or static error need not borrow an input that only controls its contents or selection.
   - an indirect call, whose outputs conservatively derive from all read-only arguments and the callee's captured origins; a bind (§4) copies all read-only arguments and the callee's captured origins. Arguments passed to `mut` fields do not count.

   Summaries track parameters as whole values, not individual fields. Reads through pointers and slices preserve their input origins. Pointer-bearing stores through mutable caller storage or dereferences conservatively taint pointer-bearing outputs and propagate through calls, even if a call's result is discarded. Generic store types are substituted at direct calls, so copying bytes does not count as storing pointers. Unknown calls conservatively may store their read-only inputs and captured origins. Calls inside recursion retain conservative dependencies. Only a declared top-level `!T` result has separate output channels; generic results and projections or aggregates containing errors conservatively merge their origins. Local `!T` values and pattern payloads may also combine success and error origins; no written function type carries a borrowing contract.

   Only values whose type contains a pointer carry this. An error type (§8, Errors) contains one if an error of its set has a payload that does, and a `!T` if its `T` or its error type does. A `&fn` contains one; the places it holds follow §6. A string literal view or a view into const array storage is derived from nothing.
3. It is a compile error to:
   - `return` a value derived from any local or read-only context field of the function
   - `try e` (§8, Errors) when the error output is derived from a local or read-only context field of the function: `try` may return the error
   - assign a value derived from `L` to a local declared in a scope outside `L`'s
   - assign a value derived from `L` to a `mut` context field or any part of one
   - assign a value derived from `L` to a place that goes through a deref

   While the bodies are checked a function's error set isn't known yet, so a value of its error type is taken to contain a pointer if any error of the program has a payload that does. An error above that only such a set could cause is reported once the sets are inferred, and only if the set has an error whose payload contains a pointer.
4. Not checked: a callee storing a read-only pointer argument through its own `mut` field, and a pointer returned from a `&p` passed to a `mut` field. These remain undefined behaviour if the memory no longer exists (§12).

## 15. Capabilities and the entry point

```
capability Glfw                                   // permission to call a C library (§18)

namespace gl {
    capability Gl1_1 { clear: extern fn{ mask: u32 } }                    // permission to call OpenGL: its functions
    capability Gl2_0 { ..Gl1_1, use_program: extern fn{ program: u32 } }  // 1.1's, and those 2.0 added
}

namespace os { capability Proc { extern environ: *?c::String } }   // a C variable, read only in os

fn main { mut io: Io, mut fs: Fs, mut glfw: Glfw, args: Args } -> i32 { ... }

fn clear { mut gl: gl::Gl1_1 } { gl.clear{ mask = gl::COLOR_BUFFER_BIT } }  // a call through it

let mut gl = gl::load_2_0{ get_proc = glfw::proc_address{ &glfw, _ } } ifnull { return 1 }   // only gl's functions make one
clear{ &gl }                                      // a Gl2_0 includes a Gl1_1
```

1. `capability Name` declares a **capability type**: permission to have some effect (§1.3). It has no generic parameters and no zero value. Without fields it takes no space; with them (rule 5) it is a struct of C functions. C variables (rule 12) and statics (rule 13) take no space, and a capability whose only fields are these counts as one without fields.
2. Nothing can construct a capability without fields: `Name{}` is an error. The only ones are those `main` receives, which it passes down to the functions that need them, and those a callback receives when C calls it (§18 Callbacks), on the binding's word that C calls it only while they are held.
3. std declares `Io` (console, §17 `io`), `Fs` (files, §17 `fs`), `Mem` (memory beyond the stack, §17 `mem`), `Proc` (other programs and the environment, §17 `proc`) and `Build` (a build program's, §19). A binding of a C library declares its own, and its extern fns with effects take it (§18).
4. A capability is permission for code that follows the rules, not a sandbox: a pointer `@cast` (§13) can forge one, as it can corrupt any memory.
5. `capability Name { field: extern fn{C} -> R, ... }` declares one with **fields**: C functions it holds, such as a library's looked up at run time. Each field is a C function pointer (§12), never null; a `?extern fn` isn't allowed, since unwrapping it would read the field (rule 7). Its layout is a struct's.
6. Only a function declared directly in the namespace that declares it, whose context holds a capability or a bound function (`&fn`, §6), can construct one, with a literal (`Name{ field = f, ... }`, §7). Holding one means that function made it. These are how effects reach a function (§1.3): a bound function may hold a capability, as a loader bound to a library's does (`glfw::proc_address{ &glfw, _ }`), so a binding can take one without naming the library it comes from. Code that holds no capability has none to bind a loader to. A loader that holds none can't look a function up: short of a `@cast` (rule 4), it returns `null` or a named function of the type it returns, which is pure if that type takes no capability (§18).
7. Its fields can only be called: `x.f{ ... }` calls the function field `f` holds, and `x` must be a mutable place, as for passing it to a `mut` field (§3); through a `*mut` to one, `p.f{ ... }` calls it too. Holding `x` is the permission, so the field's type needs no capability field. Reading a field as a value (`let g = x.f`, passing, comparing, casting or taking its address) or assigning one is an error: it would reach code whose signature doesn't name the capability.
8. One may be a local, a function's field, a result or an optional's payload, and copies as a struct does, but is never replaced: assigning to a place that is or holds one, as a field, an element or a payload, is an error, except the one assignment of a `let x: T` (§11, Initialization). So the functions a capability holds never change, and a copy of it is the same as it (rule 10). Neither the runtime nor C can make one, so `main` can't take one (Entry point, rule 2), nor can a callback (§18 Callbacks, rule 4). An extern fn may take one as any capability: it isn't passed to C.
9. `..Name` among a capability's fields **includes** `Name`, a capability with fields: it has `Name`'s fields where `..Name` stands, so through `Name` it has those of what `Name` includes. Its own fields and any number of inclusions may come in any order: `capability MyGl { ..Gl3_3, ..ArbDebug }`. A field reaches a capability only once: one of its own that an included one has, or one that two included ones share, as with both `..Gl3_0` and `..Gl2_0` when `Gl3_0` includes `Gl2_0`, is an error. So is including itself, directly or not. A capability with fields may include only capabilities with fields: a function of its namespace makes it (rule 6), and could otherwise give away the permission of one that only `main` receives. One without fields may include any capability, as std's `Proc` includes its platform's `os::Proc` (§17).
10. A capability converts implicitly to one it includes, directly or not, wherever §11 Widening rule 1 applies: a copy of the functions they share, which rules 7 and 8 keep from changing. A `mut` field of the included type takes a pointer to the including one (§3, rule 4): `draw{ &gl }` for `draw { mut gl: Gl2_0 }` with `gl: Gl3_3`, which §3.1 treats as any `&gl`. If the included one's fields are the first of its own, as when `..Gl2_0` is the first item of `Gl3_3` or of its first inclusion, the callee gets that pointer; otherwise it gets the address of a copy of them, which no program can tell apart from it, since neither changes. Structs, other pointers and `?A` don't convert this way (§11, Widening, rule 5).
11. In a capability's literal, where rule 6 allows one, `..e` supplies from `e` the fields of `e`'s type, which must be a capability the literal's includes: `Gl3_3{ ..base, vertex_attrib_divisor = @cast(_, p), gen_samplers = @cast(_, q) }`. Every field is still supplied exactly once, by a spread or by name. `e` is evaluated before the other items. `..e` in any other braces is an error.
12. `extern name: T` among a capability's fields declares a **C variable**: the C global `name`, or the one `#c::symbol{ name }` on the line before gives (§18), of a type C stores: a number, `bool`, an enum, a pointer or `?*T`, a struct, an extern union or a C function pointer. The linker supplies it, not a literal, so it takes no space (rule 1). `x.name` reads it, through the capability, one that includes it, or a pointer to either, only in a function declared directly in the namespace that declares the capability. That namespace wraps it for every other caller, as a platform layer wraps `environ` (§17). A read is the variable's value at that moment, which C may change. It isn't a place: it can't be assigned or have its address taken. An including capability has the variables of what it includes, and a name reaches a capability only once, as a field or a variable (rule 9).
13. `static name: T` among a capability's fields declares a **static**: storage for one `T` for the whole program, which starts as `T`'s zero value (§11, Initialization), so `T` must have one. There is one for the program, however many capabilities include it, and it takes no space in them (rule 1): a capability holds no state, since the runtime and C make fieldless ones from nothing (rule 2; §18 Callbacks), but it is the only way to reach some. `static` is a keyword only there, before a name. `x.name`, through the capability, one that includes it, or a pointer to either, is a place, only in a function declared directly in the namespace that declares the capability, as for a C variable (rule 12). It is mutable when `x` is: a `mut` field, a `let mut`, or through a `*mut`. A read-only capability reads it, and other capabilities that include it reach the same storage. It is a place through a deref (§3.1, rule 6; §14, Escape check): `&x.name` points to storage that outlives every frame, even when `x` is a local, and the escape check keeps a stack pointer from being stored in it. `#c::symbol` doesn't apply to it. An including capability has the statics of what it includes, and a name reaches a capability only once (rule 9).
    - `#stack_limit` on a `usize` static makes it the **stack limit**: on entry, every function compares its frame's address to it and panics with "stack overflow" below it. 0, the static's start, checks nothing, and a panic sets it to 0 before the panic fn runs (Entry point, rule 6). std's `rt::Stack` has one, which std's start sets. A program may declare its own, which replaces std's, only if it has its own start fn too, since std's sets std's; a start fn of a program's own without one leaves std's at 0, so nothing is checked.

### Entry point

1. `fn main { ... }` is the entry point.
2. Every field of `main` must have a capability type without fields (C variables and statics don't count, §15 rules 12 and 13), except a read-only field `args`. The runtime supplies them. A program declares only the ones it uses.
3. `args: Args` holds the command-line arguments that follow the program, as bytes. `Args` is a top-level std alias for `[][]u8` (§17), so either spelling is accepted.
4. `main` may return `i32`: the program's exit code. Without a return type it exits with 0.
5. `#start` on a fn makes it the program's **start**, which runs `main`: the runtime calls it first, and the program's exit code is its result, an `i32`. Its context is capabilities without fields, which the runtime supplies as `main`'s, and any of these read-only fields: `argc: i32` and `argv: *?*u8`, C's; and `main: &fn{ args: Args } -> i32`, which calls `main` with its capabilities and `args`, and gives its exit code. std's (§17, `rt`) gives the runtime memory for function values' records (`pages_set`, beyond the little the runtime keeps itself), sets up the platform, sets the stack limit (§15, rule 13), gives `main` its `args`, and writes standard output's buffer out once `main` returns. A start fn of a program's own that doesn't call `rt::pages_set` has only the runtime's own: past it, a bind or conversion that needs a record panics.
6. `#panic` on a fn makes it the program's **panic fn**: every panic calls it, `@panic` and the checks that panic alike. Its context is capabilities without fields, supplied as for `#start`, and any of these read-only fields: `msg: []u8`, the message; `file: []u8`, `line: u32` and `col: u32`, the panic's position, with a line of 0 for a panic without one, whose file is the program's path. It returns nothing, and it shouldn't return at all: the program stops at once if it does, or if it panics. Its own frames aren't checked for stack overflow, so it can report one. std's (§17, `rt`) writes standard output's buffer out, then `FILE:LINE:COL: panic: MSG` (or `PROGRAM: panic: MSG`) to standard error, and exits with 134.
7. Each is a fn with a body and no generic parameters, and neither may take a `Build` (§19). std declares one of each. A program's own replaces std's, so a program for a target without an OS can supply both; one with neither has no start, and a panic stops it at once. Two in the program, or two in std, are an error.

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

1. The standard library is ctxlang source (`std/*.ctx`) and one platform layer: `std/os/windows`, or for Linux and macOS `std/os/posix`, which they share, with `std/os/linux` or `std/os/macos` beside it. It is part of every program, with the layer of the platform it is built for. `ctxc interp` builds a program with the interpreter's layer, `std/os/interp`, instead, and the `target.ctx` of the platform it runs on; there, a `#start` fn's `argv` (§15, Entry point) is UTF-8 on every platform, where Windows' C gives the ANSI code page's bytes. Its extern fns (§18) are the operating system's and the C library's, except for a few that the runtime provides in C: panics without a position and memory for function values' records (`rt`), and floats as text and back (`ascii`), which a program links only if it uses them. Its state for the whole program is statics (§15, rule 13).
2. Its namespaces are visible from user code as if declared at top level. A user declaration with the same name shadows a std one (§10).
3. It allocates only through an allocator the caller passes in (§14), and does IO only through an `Io` or `Fs` the caller passes in (§15). Only `mem::pages` takes memory from the system, through a `Mem` the caller passes in.
4. A platform layer declares namespace `os`: what the rest of std needs from the operating system, over extern fns to the OS's own C functions and, through its capability `os::Proc`, C variables (§15, rule 12). Every layer declares the same functions and an `os::Proc`, so std's other files are the same on every platform, and each function that can fail declares the same set (§8, Errors, rule 14), `fs::Error` or `proc::Error`, whichever of it its OS gives, so a program checks the same on every platform. Linux's and macOS's share `os` and differ in namespace `sys`: the C library's numbers and layouts, and the functions it names differently. What the platform is, apart from how it is reached, is namespace `target`, in each platform's `target.ctx`: `OS`, `ENV_CASE` and `is_absolute`. The interpreter's layer, `std/os/interp`, is over extern fns that only `ctxc interp` provides (`ctx_interp_*`); what it can't do (standard input, files, other programs) stops the run.

| Namespace | Contents |
|---|---|
| `slice` | Helpers for built-in slices (§12): `empty`, `cast`, `copy`, `fill`, `eq_bytes` |
| `c` | What calling C needs (§18): the attribute `symbol { name: []u8 }`; `String { ptr: *u8 }`, C's NUL-terminated `const char *`, which a literal can be (`from_literal`, §18, which fails with `has_nul{ at }`), with `len` (the bytes before the NUL), `bytes` (a view of them) and `copy` (bytes and a NUL from an allocator; fails with `c::has_nul{ at }` or `alloc::out_of_memory`). |
| `Args` | Declared at the top level: `type Args = [][]u8`, the type of `main`'s `args` (§15). |
| `Io`, `Fs`, `Mem`, `Proc`, `Build` | Declared at the top level: `capability Io` and so on (§15), in `io.ctx`, `fs.ctx`, `mem.ctx`, `proc.ctx` and `build.ctx`. `Proc` includes `Io`, since the programs it starts share the console, and `Build` includes `Io`, where a build's graph goes without `CTX_BUILD_OUT` (§19). Each includes its namespace's `State` too (`io::State`, `proc::State`, `build::State`): std's state for the whole program, as statics (§15, rule 13). |
| `rt` | What starts a program and reports its panics (§15, Entry point): `start`, std's `#start` fn, and `report`, its `#panic` fn. `Stack`, a capability whose `#stack_limit` static `limit` is the stack limit (§15, rule 13), which `start` sets. `c_args` gives a layer the command line's arguments from C's `argv`. `pages_set` gives the runtime `record_pages` or another fn for memory for function values' records. `fail` panics without a position, with a message that needn't be a literal; `Message`, `message`, `add`, `add_u64` and `fail_with` build one. |
| `proc` | `Proc` includes the layer's `os::Proc` (rule 4) and `Io`. The errors `not_found`, `permission_denied` and `other{ code }`; `run` (starts a program found on PATH, with extra `KEY=VALUE` environment entries, sharing standard input and output, and returns its exit code, a `!i32`: 128 + N if signal N killed it), `spawn` (starts one as `run` does without waiting for it, a `!Child`) and `wait` (waits for a `Child`, once, and returns its exit code as `run` does), `processors` (how many processors the program may run on), `env` (an environment variable, or null), `environment` (the environment's `KEY=VALUE` entries), `exe_path` (this program's executable), `os` (the operating system, a `build::Os`). Every function takes `mut proc: Proc`. |
| `build` | Build programs (§19): `Exe`, `Os` (`windows`, `macos`, `linux`); `exe`, `add_sources`, `optimize`, `link`, `framework`, `lib_path`, `os`. Every function takes `mut b: Build`. |
| `fs` | `File`, `Mode` (`read`, `write`, `append`, `create`); the errors `not_found`, `permission_denied`, `is_directory`, `exists`, `not_directory`, `bad_file` and `other{ code }` (the OS's number); `open`, `read`, `write`, `seek` (to an offset from the start), `read_at` (fills a buffer from an offset, short only at the end of the file), `close`, `size`, `remove`, `make_dir`, `rename` (replacing any file at the new path), and `read_all` (into memory from an allocator), `write_all`, `list` (a directory's entry names, sorted, into memory from an allocator) and `make_absolute` (a path joined to the working directory unless it is absolute, into memory from an allocator); `is_absolute`. Every function but `is_absolute` takes `mut fs: Fs` and returns a `!T`, or a bare `!` (`close`, `remove`, `make_dir`, `rename`), that fails with the errors its body can produce (§8, Errors), and `read_all`, `list` and `make_absolute` with `alloc::out_of_memory`. A `File`'s `id` is the OS's handle: a file descriptor, or a Windows HANDLE. The platform layer does the work (`os`, below). |
| `alloc` | `Bytes` (`[]mut u8`), the allocator type `Fn(S)`, the error `out_of_memory`, typed `resize(T, S)`, and `new(T, S)` and `free(T, S)` for one `T`: `new` returns a `!*mut T` holding the given `value`. `resize` and `new` fail with `out_of_memory`; resizing to 0 frees and doesn't fail. |
| `mem` | `PAGE` (4096); `pages`: at least `size` bytes of zeroed, page-aligned memory (`size` rounded up to a multiple of `PAGE`), as a `?alloc::Bytes`, valid until the program ends, or null; `reserve`: the same for an arena's buffer, made usable as the arena reaches it, so a generous size costs address space rather than memory (on Windows, where `pages` commits all of it), and only an arena may use it. Both take `mut mem: Mem`. |
| `os` | The platform layer (rule 4): `OS`, the `build::Os` it is for; `write` (some of the bytes, which aren't empty, to an `io::Stream`; how many, 0 after an error), `read` (some of standard input; 0 at the end or after an error), `pages` (zeroed, page-aligned memory of a size that is a multiple of `mem::PAGE`, or null), `reserve` (the same for an arena, reserved) and `commit` (makes an arena's memory usable as it reaches it), `env` (an environment variable, or null), `environment` (the environment's `KEY=VALUE` entries); for `rt`, `start` (what the platform needs before `main` runs), `args` (the command line's arguments) and `exit`; for `proc`, `spawn`, `wait`, `processors`, `exe_path` and `ENV_CASE` (whether the environment's keys are case-sensitive); and for `fs`, over paths that aren't empty: `file_open`, `file_read`, `file_write` (some of the bytes), `file_seek`, `file_close`, `file_size`, `remove`, `make_dir`, `rename`, and `Dir` with `dir_open`, `dir_next` (the next entry's name, or null) and `dir_close`, which fail with `fs`'s errors; `working_dir` (the working directory's path, into a buffer) and `is_absolute`. `Proc`, a capability without fields that std's `Proc` includes: on posix it names C's `environ` (§15, rule 12), on Windows nothing. `write` and `read` take `mut io: Io`; `pages`, `reserve` and `args` (with `argc: i32` and `argv: *?*u8`) `mut mem: Mem`; `commit` (`first` and `last`, `*u8`s) and `is_absolute` nothing; `start` `mut io: Io`, `mut proc: Proc` and `argv`; `env`, `exit`, `spawn`, `wait`, `processors` and `exe_path` `mut proc: Proc`, the layer's own; the rest `mut fs: Fs`. `io`, `mem`, `proc` and `fs` call them, so they are the same on every platform. |
| `arena` | `Arena`, a bump allocator: `new`, `alloc` (an `alloc::Fn(Arena)`, which makes memory from `mem::reserve` usable as it reaches it), `reset`, `remaining` |
| `list` | `List(T, S)`: `new`, `reserve`, `push`, `pop`, `get`, `set`, `at`, `items`, `clear`, `each`, `free`. `new` takes the allocator's function and a pointer to its state, and the list keeps both, so it must not outlive the state (§14). `reserve` and `push` return a bare `!` that fails with `alloc::out_of_memory`, leaving the list as it was. |
| `map` | `Map(K, V, S)`, a hash map that holds its allocator as a list does, and its key type's hash and equality functions: `new`, `len`, `has`, `get`, `at`, `put`, `remove`, `clear`, `free`, `next`, `each`. `put` returns a bare `!` that fails with `alloc::out_of_memory`, leaving the map as it was. `hash_*` and `eq_*` for `i32`, `i64`, `u32`, `u64`, `usize`; `hash_bytes` for byte slices, with `slice::eq_bytes`; `hash_string` for `utf8::String`, with `utf8::eq`. |
| `ascii` | Byte-level character tests and case for a `u8`: `is_digit`, `is_upper`, `is_lower`, `is_alpha`, `is_alnum`, `is_space`, `to_upper`, `to_lower`. Extern fns, used by `utf8`'s numbers, which the runtime provides in C (`ctxc/rt/ctxfloat.c`): `f64_digits`, `f32_digits`, `f64_parse`, `f32_parse`. |
| `utf8` | `String { bytes: []u8 }`, the text type: a non-owning view of valid UTF-8. Offsets are in bytes, and an offset inside a character panics; a character is a `u32` code point. `from` (checks the bytes, returning a `!String` that fails with `invalid{ at }`, the offset of the first bad byte), `from_literal` (a literal's conversion, §18: `from` while compiling), `of` (panics if invalid), `empty`, `len` (bytes), `count` (characters), `is_boundary`, `at`, `sub`, `eq`, `starts_with`, `ends_with`, `find`, `find_str`, `split_once`, `trim`, `trim_start`, `trim_end`, `encode`, `is_scalar`, `is_ascii`. Character tests and case (ASCII only). `parse_i64`, `parse_u64`, `parse_f64`, `parse_f32`, `fmt_i64`, `fmt_u64`, `fmt_f64`, `fmt_f32`. `Cursor`: a read position for lexers, by character: `cursor`, `done`, `rest`, `peek`, `peek_at`, `bump`, `eat`, `eat_str`, `take_while`, `skip_space`. `Builder(S)`: a growable string that owns its bytes and holds its allocator as a list does, with `push`, `push_char`, `push_i64`, `push_u64`, `push_f64`, `push_f32`, `push_bool`, `view`, `clear`, `free`. Its `@fmt` writers (§13, Formatting), marked `#write`, are `push` for a `String`, `push_literal` for a `strlit`, `push_bytes` for a `[]u8` (and so a `[]mut u8`: a byte that starts no valid UTF-8 sequence becomes U+FFFD), `push_bool`, `push_f32`, `push_f64`, and `push_` and the type for each integer type (`push_i8` ... `push_usize`); `push_char` isn't one. For a hole written another way: `write_hex`, `write_char`, and padded to a width with spaces, or zeros after any `-`: `push_padded` (a `String`), `push_int`, `push_uint`, `push_hex`. `Fmt(S)` is a writer into a `Builder(S)`, `&fn{ mut b: Builder(S) } -> !`. Each push and write returns a bare `!` that fails with `alloc::out_of_memory`. `fmt_hex` writes an unsigned integer in hexadecimal into a buffer. |
| `math` | The C library's math functions, with libm's names, pure: for `f64`, `sqrt`, `cbrt`, `hypot`, `pow`, `exp`, `exp2`, `log`, `log2`, `log10`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `sinh`, `cosh`, `tanh`, `floor`, `ceil`, `round`, `trunc`, `fabs`, `fmod`, `fmin`, `fmax`, `copysign`, and each with an `f` suffix for `f32` (`sqrtf`). `PI`, `TAU`, `E`, `PI_F32`, `TAU_F32`; `is_nan`, `is_inf`, `is_finite` (an `f64`, which an `f32` widens to). |
| `io` | `Stream` (an enum: `out`, `err`); `print`, `println`, `eprint`, `eprintln` for `utf8::String`, `newline`, `put_char` (one character), `print_i64`, `print_u64`, `print_f64`, `print_f32`, `print_bool` and their `println_` forms (smaller number types widen to these), `read_line` (bytes that aren't valid UTF-8 become `?`), `write` and `read` (bytes), `flush`, `put` (bytes past the buffer, through `os::write`). `@fmt` writers onto an `Io`, to standard output (`_ = @fmt(&io, "{} files\n", n)`), and onto a `Stderr`, which `to_stderr` makes from one: `write_` and the type, and `ewrite_` and the type, for a `strlit` (`text`), `utf8::String` (`string`), `[]u8` (`bytes`, as they are), `c::String` (`cstring`), `bool`, `f32`, `f64` and each integer type. They don't fail. Standard output is buffered: it is written out before anything goes to standard error or is read from standard input, and when the program ends or panics. The buffer is io's static (§15, rule 13), since a panic flushes it too: `State`, a capability that `Io` includes, whose `out` is an `Out`. |

```
fn main { mut io: Io } {
    io::println{ &io, s = "hello" }                    // a utf8::String viewing static bytes (utf8::from_literal)
    io::println_i64{ &io, n = 42 }
}
```

## 18. C functions and attributes

```
#c::symbol{ name = "labs" }
extern fn long_abs { n: i64 } -> i64

extern fn frexp { x: f64, mut exp: i32 } -> f64
extern fn glfwPollEvents { mut glfw: Glfw }      // a capability says who may call it
```

### Attributes

1. `#path` or `#path{ field = e, ... }`, on its own line before a declaration or a capability's field, is an **attribute** of it. Either may have several.
2. `path` names a struct, and the braces are a literal of it, checked as a const's initializer is and folded (§14): it can't call a function or use a const that isn't folded. `#path` alone means `#path{}`.
3. Attributes are data. The compiler acts on those of std's `c` namespace (`c::symbol` on an extern fn or a C variable, `c::callback` on a fn) and ignores the rest; a program can read them later (PLAN.md, stage 3).
4. The compiler declares `convert` (Literal conversions, below), `write` (§13, Formatting), and `start` and `panic` (§15, Entry point) itself. They have no namespace, and a declaration of the same name shadows one.

### Extern functions

1. `extern fn name { context } -> R` declares a function that C provides. It has no body and no generic parameters.
2. It calls the C symbol `name`, or the one `#c::symbol{ name = "..." }` gives. The symbol must be a C identifier.
3. Its context fields are C's parameters in the order they are declared. A field with a capability type (§15) isn't passed: it only says who may call the function. A `mut` field of type `T` is passed as a `T*`.
4. A field or result may have a numeric type, `bool`, an enum (as its base type), a pointer (as a C pointer), a `?*T` or `?*mut T` (as a C pointer, with `null` as `NULL`: §8, Optional, rule 6), a C function pointer `extern fn{C} -> R` or its `?` (§12), a `c::String` or `?c::String` (as a `const char *`, below), a slice (as a struct of `ptr` and `len`), a struct (as a C struct of the same layout) or an extern union (as a C union, §12). Other types are an error, other optionals included.
   A `c::String` is C's `const char *`: a struct around one pointer, which C takes and returns as the pointer, and a `?c::String` is one that may be `NULL` (§8, Optional, rule 6). A literal where one is expected points to its bytes, which the hidden zero ends (`c::from_literal`; §11, Literals). A `c::String` built from any other `*u8` (`c::String{ ptr = p }`) must point to bytes that end in a NUL; that isn't checked.
5. Every call goes through a declaration of the symbol made for that function, so it can't clash with the declaration of the same symbol in a C header. Nothing checks the declaration against C's: a wrong one is undefined behaviour.
6. An extern fn is called like any function and is a value of type `fn{C} -> R`; where an `extern fn{C} -> R` is expected, it is its C symbol's address instead (§12, C function pointers).
7. Every program is linked with the C library and the math library.

8. §1.3 holds by declaration: an extern fn that reaches IO, the OS or memory outside its pointer arguments must take a capability for it. One without a capability field, such as `sqrt`, promises to be pure. The compiler can't check either.

9. C's global variables have no declaration of their own: a capability names them, `extern name: T` among its fields, and only its namespace reads them (§15, rule 12). Reading one is as much an effect as calling an extern fn that takes the capability.

### Literal conversions

```
namespace utf8 {
    #convert
    fn from_literal { s: strlit } -> !String { return from{ bytes = s.bytes } }
}

namespace regex {                                // a program's own type
    #convert
    fn from_literal { s: strlit } -> !Regex { return compile{ s.bytes } }
}

io::println{ &io, s = "hello" }                  // utf8::from_literal, run while compiling
let r: regex::Regex = "[a-z]+"                   // a bad pattern is a compile error
```

1. `#convert` on a fn makes it a **literal conversion**: a string literal where the type `T` of its result is expected is the fn's result for the literal (§11, Literals). Any namespace may declare one, for any `T`, so a library can give literals to a type it doesn't own.
2. The fn has a body and no generic parameters. Its context is one read-only field of a literal type, `s: strlit`, so it takes no capability and can run while compiling. Its result is a `T` or a `!T`, where `T` isn't a `strlit`, a `[]u8` or a `[N]u8`, or a `?` of one, which a literal is without one.
3. "Expected" is where widening applies (§11, Widening, rule 1), a const's initializer, an `if` or `match` branch next to one of type `T` (§11, Literals), and a call's `strlit` field, so `utf8::from_literal{ s = "hi" }` calls one directly, as any fn. Where a `?T` is expected, a conversion to `?T` comes before one to `T`. Only literals convert: no other value does, and conversions don't chain.
4. A literal sees only the conversions its code could name (§10, Name lookup): those in its namespace or one around it, or in a named namespace inside one of those, as `a::b::` names it. The program's top level has no name, so std's code sees only std's conversions, and the program's sees std's and its own. Two conversions to one `T` that a literal sees are an error at it, naming both, and not before: two libraries may each declare one, and a program may call either.
5. The conversion runs once the bodies are checked, as a const's initializer does (§14), and the program holds its result. The same limits apply, and the result may hold no pointer but one into the literal's bytes. An error result is a compile error at the literal, printed as `@fmt` writes an error (§13), with each field a number or a `bool`, or `_` for any other type: `string literal: utf8::invalid{ at = 3 }`. A const whose initializer holds a converted literal is run, not folded, and an attribute can't hold one.

### Callbacks

```
type KeyFn = extern fn{ mut glfw: Glfw, window: *mut Window, key: i32, scancode: i32, action: i32, mods: i32 }
extern fn glfwSetKeyCallback { mut glfw: Glfw, window: *mut Window, cb: ?KeyFn } -> ?KeyFn

#c::callback
fn on_key { window: *mut Window, key: i32, action: i32 } { ... }

_ = glfwSetKeyCallback{ &glfw, window, cb = on_key }
```

1. `#c::callback` on a fn lets C call it. The fn has a body and no generic parameters, and its fields and result follow an extern fn's rules (rule 4 above).
2. Where an extern fn type `extern fn{Cs} -> Rs` is expected (or its `?`), the callback's name is a C function of that type, which calls it. The callback must be accepted where `fn{Cs} -> Rs` is (§5): each of its fields is one of `Cs`, with the same type and mutability, and its result is `Rs`. Fields of `Cs` it doesn't take are dropped, and the order of its own fields doesn't matter.
3. Only the name converts. A function value, a bind or a callback stored in a local doesn't (§12, C function pointers, rule 5).
4. C doesn't pass capability fields (rule 3 above), so the callback receives them without C passing them. Declaring a capability in a callback type is the binding's promise that C calls it only while that capability is held: for GLFW, within the call that polls events. The compiler can't check it. A capability with fields (§15, rule 5) can't be one of them, in the callback's fields or in the type its name converts to: nothing could supply it.
5. State reaches a callback through C: a pointer the library hands back (a `void *` user pointer, typed as the binding chooses), or a `mut` field, which is C's pointer.
6. C must call a callback on the thread that called into C. Calling it from another thread is undefined behaviour.
7. A callback is still a fn: ctxlang code may call it, and use it as a `fn` value.

## 19. Build programs

```
// tools/viewer/build.ctx: a tool, made of its own directory and of libraries other programs share
fn build { mut b: Build } {
    let exe = build::exe{ &b, name = "viewer", root = "." }
    build::add_sources{ &b, exe, dir = "../../lib/formats" }
    build::add_sources{ &b, exe, dir = "../../lib/platform" }
    build::optimize{ &b, exe, level = 2 }
    build::link{ &b, exe, lib = "SDL2" }
    match build::os{ &b } {
        macos   => { build::lib_path{ &b, exe, path = "/opt/homebrew/lib" } }
        windows => { build::link{ &b, exe, lib = "gdi32" } }
        linux   => {}
    }
}
```

1. A program that is a directory may have a `build.ctx` at its top: its **build program**, compiled and run before anything else is built. It describes the executables to build, which files each is made of, and how each is compiled and linked. Platform choices are ordinary code.
2. A build program is a program whose entry point is `fn build` instead of `fn main`: §15's rules for `main` apply to it. A program with a `main` has no other entry point, and a `fn build` in it is an ordinary function.
3. Only `build` may take a `Build` (§15): `main` can't, nor a `#start` or `#panic` fn. A `Build` includes an `Io` (§17).
4. `build::exe{ &b, name, root }` names an executable built from the `.ctx` files of directory `root`, not of its subdirectories, and returns a `build::Exe` for the calls that add to it. Two executables of one build can't have the same name. `build::os` is the operating system the build is for.
5. `build::add_sources{ &b, exe, dir }` adds the `.ctx` files under directory `dir`: those in it and in its subdirectories, at any depth. So libraries can live in directories of their own, which several programs add. A file that two directories reach, or one directory twice, is compiled once.
6. `build::optimize{ &b, exe, level }` compiles the executable's C at optimization level 0 to 3 (`-O0` to `-O3`) instead of 1. The other flags stay (PLAN.md, How ctxlang maps to C).
7. `link` adds a library (`-l`), `framework` a macOS framework, and `lib_path` a directory to find libraries in (`-L`).
8. Paths are relative to the directory `build.ctx` is in, and may leave it through `..`. Errors name an executable's files by their paths from the working directory, without `.` or `..` (`lib/formats/gff.ctx`). A file named `build.ctx` is never one of an executable's files.
9. Names, roots, directories, libraries and paths can't be empty or hold a tab or a line break, a name can't hold `/`, `\` or `"`, and a level is 0 to 3: the build panics.
10. `ctxc run PATH [-- ARGS...]` builds the program at PATH (a `.ctx` file, or a directory, with or without a `build.ctx`) and runs its first executable; `ctxc exe PATH -o OUT` writes that executable to OUT. Only ctxc and a C compiler are needed (PLAN.md, "Working on ctxc").
11. A build writes only under ctxc's home, in `build/run`, in a directory of the program's own, which its absolute path names: ctxcs building different programs at once don't meet. A big program's C is several units, grouped by the files that declare their functions, which are compiled at once; a unit whose C, runtime, C compiler and flags are the same as when it was last built isn't compiled again, so an edit recompiles only the units of the files it touched (ctxc/drive.ctx, ctxc/emit_c.ctx).
