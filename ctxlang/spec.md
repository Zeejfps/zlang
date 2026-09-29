# ctxlang: spec draft

Examples: [examples/list.ctx](examples/list.ctx) (lists, allocators, bound functions), [examples/wordcount.ctx](examples/wordcount.ctx) (files, arguments, maps), [examples/json](examples/json) (a JSON parser and printer, as a program of several files: `python -m ctxi examples/json FILE`).

## 1. Top level

1. A program is a sequence of declarations: `fn`, `struct`, `union`, `type`, `const`, `namespace`.
2. There is no mutable state at top level. Top-level names may be referenced from anywhere.
3. All effects (IO, memory, OS) reach a function only through its context.

## 2. Functions and contexts

```
fn name(Generics) { field: T, mut field: T, ... } -> R { body }
```

1. The `{ ... }` after the name is the **context**. It is the function's only input.
2. A context field is read-only unless marked `mut`.
3. A function can't assign to a read-only field or any field or element of it. Memory reached through a pointer inside it is not part of it (§12, Pointers).
4. `-> R` may be omitted. The function then returns no value.
5. Two fields in one context can't share a name.
6. A `mut x: T` field holds a `*T`. Inside the function, `x` is the place of type `T` it points to, and `&x` gives the `*T`.

## 3. Calls

```
f{ a = expr, b = &place, c, &d, .. }
```

1. A call is an expression of function type followed by `{ ... }`.
2. Every context field of the callee must be supplied exactly once. Order doesn't matter.
3. A read-only field of type `T` takes an expression of type `T`.
4. A `mut` field of type `T` takes an expression of type `*T`. If the argument has the form `&p`, `p` must be a mutable place and §3.1 applies. Any other `*T` expression is accepted unchecked.
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
6. Pointers that don't come from `&p` in the call itself are not checked, and neither are places that go through a deref.

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

1. `Rg` is identical to `Rs`, and
2. for every field `n: T` in `Cg`, `Cs` has a field `n` with an identical type `T`, and
3. if the field `n` is `mut` in `Cg`, it is `mut` in `Cs`.

`Cs` may have fields that `Cg` lacks. Those fields are dropped when the value is called.

## 6. Bound functions

1. `&fn{C} -> R` may only be the type of a local or of a read-only context field. It can't be a return type, a struct field type, a union payload type, an array element type, the `T` of `?T` or `*T`, or the type of a `mut` context field.
2. A bound function can't be assigned to a local declared in a scope outside that of any place it holds (§3.1.3, including places held through nested binds).
3. A bound function may be stored in a local and passed as a call argument.
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
match (e) {
    variant{ f, g } => { ... }
    variant         => { ... }
    else            => { ... }
}
```

1. The arms must be exhaustive. `else` matches every variant not listed, and must come last. `else` is an error if every variant is already listed.
2. Each variant appears in at most one arm.
3. A pattern `variant{ f }` binds payload field `f` as a read-only local. `variant{ f = x }` binds it under the name `x` instead. A pattern may bind a subset of the fields.
4. If the scrutinee has type `*U` for a union `U`, the match goes through the pointer. In its arms, `&f` binds payload field `f` as a mutable place, and `&f = x` binds it as `x`.
5. `&f` in a pattern is an error unless the scrutinee is a pointer.
6. If the scrutinee is `&p`, no place that overlaps `p` (§3.1) may be accessed inside an arm except through that arm's bindings. For other pointer scrutinees this isn't checked.
7. `match` is a statement, and can also be an expression (§11, If and match expressions).
8. To take one variant apart and leave on any other, use `let` with a pattern (§11, Let-else).

### Optional

1. `?T` is a built-in union with variants `null` and `some{ value: T }`.
2. `null` is a value of every `?T`. An expression of type `T` converts implicitly to `?T` as `some{ value = expr }`.
3. Narrowing: in `if (x != null) { B }`, `x` has type `T` in `B`. In `if (x == null) { } else { B }`, `x` has type `T` in `B`. `x` must be a `let` local or a read-only context field. To narrow a mutable one, copy it first (`let y = x`) or `match` on it.
4. Narrowing after an `if` statement: if the branch where `x` is null always leaves (it ends a path, §11.7, 8, 9), `x` has type `T` from after the `if` to the end of the enclosing block. That branch is the `{ }` of `if (x == null) { }`, or the `else` of `if (x != null) { } else { }`. `x` must be as in rule 3. A `let x` in that same block is an error if `x` was declared there, and shadows it otherwise.

```
let d = hex_digit{ c }            // ?u32
if (d == null) { return null }
v = v * 16 + d                    // d: u32
```

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
3. `::` resolves namespace members and union variants. `.` resolves struct fields.

### Name lookup

1. Names are in one of two kinds:
   - **paths:** namespaces, structs, unions, type aliases
   - **values:** locals, context fields, functions, consts
2. A name is looked up only among names of the kind its position requires:
   - the name before `::` is a path
   - a name in a type is a path
   - a name in an expression is a value
3. Lookup goes from the innermost scope outward: block locals, then context fields, then enclosing namespaces, then top level. The first match of the required kind wins.
4. A path and a value may share a name in the same scope. Two paths or two values may not.
5. A value in an inner scope shadows a value of the same name in an outer scope.

## 11. Statements and control flow

```
let x = e      let mut x = e      let x: T = e      let x: T      let mut x: T
let variant{ f, g = y } = e else { }      let ok{ value } = e else err{ error } { }
x = e
if (e) { } else if (e) { } else { }
while (e) { }
break
continue
match (e) { ... }
return e
return
defer f{ ... }      defer x = e      defer { }
f{ ... }
```

1. Conditions and match scrutinees are always in parentheses.
2. `{` after the `)` of a condition or scrutinee, after `else`, or after `=>` begins a block. `{` after any other expression begins a call or literal. In a let-else, `{` after the `else`'s variant holds its pattern if another `{` follows its `}`, and is the block otherwise.
3. Statements are separated by newlines or `;`. A postfix `{`, `[` or `(` must be on the same line as the expression before it.
4. Every block is a scope. A `let` is visible from its declaration to the end of its block.
5. In `x = e`, `x` must be a mutable place.
6. An expression statement must be a call or a builtin call. Its result is discarded. The exception is the last statement of a branch of an `if` or `match` expression, which gives the branch its value (below).
7. `return` without a value is only allowed in a function with no `-> R`. In a function with `-> R`, every path must end in `return e` or `@panic()`.
8. `break` leaves the innermost enclosing `while`. `continue` skips the rest of its body and goes to its next condition check. Both are errors outside a loop, and both end a path.
9. `while (true)` without a `break` that leaves it ends a path, like `return`.

### Let-else

```
let ok{ value = h } = half{ n } else err{ error } { return Result::err{ error } }
let some{ value = c } = peek{ p } else { return null }
let null = cached else { @panic() }
```

1. `let P = e else { B }` matches `e` against the pattern `P`, which is a variant with optional bindings as in a match arm (§8, Match). `P` may not be `mut`, and bindings may not use `&`.
2. `e` must have a union or `?T` type. A pointer is an error: use `match`.
3. If `e` holds `P`'s variant, its bindings are read-only locals from after the statement to the end of the enclosing block, as if declared by `let`.
4. Otherwise `B` runs. `B` must leave: it ends a path (§11.7, 8, 9). `P`'s bindings aren't visible in it.
5. `else V{ ... } { B }` binds `V`'s fields in `B`. `V` must be the union's only variant other than `P`'s.

### Defer

```
let mut xs = list::new(i32){ realloc = arena::alloc }
defer list::free{ list = &xs, &heap }
```

1. `defer` takes a call, an assignment or a block. Its body runs when the enclosing block exits: at its end, or through `return`, `break`, `continue`, or a branch of an `if` or `match` expression leaving (§11, If and match expressions).
2. A block's deferred bodies run in reverse order of their `defer` statements. Only `defer` statements that were reached run.
3. The body is evaluated when it runs, not at the `defer`: `defer say{ n = i }` sees the value `i` has at exit. A `return e` evaluates `e` before deferred bodies run.
4. A `defer` inside a loop body runs at the end of each iteration that reached it.
5. Deferred bodies don't run when the program stops through `@panic()`.
6. The body is checked where it appears. It can read only variables that are assigned there (§11, Initialization), and it can't assign a `let x: T` declared outside it.
7. The body can't leave: `return` is an error in it, and `break` and `continue` in it must be inside a loop that is also in it.

### If and match expressions

```
let sign = if (n < 0) { -1 } else if (n == 0) { 0 } else { 1 }
let v = match (parse{ s }) {
    ok{ value }  => { value }
    err{ error } => { return Result::err{ error } }
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
| postfix | `.f` `.*` `[i]` `{ ... }` `::x` `(G)` | left to right |
| prefix | `&` `-` `not` | |
| multiplicative | `*` `/` `%` | left to right |
| additive | `+` `-` | left to right |
| comparison | `==` `!=` `<` `<=` `>` `>=` | don't chain: `a < b < c` is an error |
| and | `and` | short-circuit |
| or | `or` | short-circuit |

1. Arithmetic and comparison apply to two operands of the same numeric type, after widening (below). If the operand types differ, the one that widens to the other is converted. If neither widens to the other, it is an error. Use `@as` or `@trunc` (§13).
2. Integer `+ - *` panic on overflow. `/` and `%` panic on a zero divisor. Use `@wrap_*` (§13) for wrapping arithmetic.
3. `==` and `!=` work on numbers, `bool` and pointers (by address), and on `?T` against `null`. Other types have no built-in equality.
4. `and`, `or` and `not` take and give `bool`. Conditions must be `bool`.

### Widening

A value of numeric type `A` converts implicitly to numeric type `B` when every value of `A` is a value of `B`:

| From | Widens to |
|---|---|
| `iN` | `iM` for M > N |
| `uN` | `uM` and `iM` for M > N |
| `u8`, `u16`, `u32` | `usize` |
| `usize` | `u64` |
| `f32` | `f64` |

1. Widening applies wherever an expression of type `B` is expected: a read-only call argument, a struct or union field, an assignment, a `let` with a type, a `return`, and the `T` of an implicit `T` to `?T` conversion. It also applies between the operands of a binary operator (rule 1 above).
2. Nothing else converts implicitly. In particular integers don't widen to floats, `usize` doesn't widen to a signed type, and `?A`, `*A` and `[N]A` don't convert to `?B`, `*B` and `[N]B`. A `mut` field's argument is a pointer, so its type must match exactly.
3. `usize` is at least 32 and at most 64 bits wide on every target, which is what makes the `usize` rows lossless.

### Literals

1. An integer literal (`42`) has an integer type that is inferred from every use within the enclosing function body, including uses of locals it initializes. If no use fixes it, it is `i32`.
2. A float literal (`1.5`, `2e3`) is inferred the same way among float types, and defaults to `f64`.
3. `true` and `false` are the `bool` values. `null` is described in §8.
4. `[a, b, c]` is a `[3]T` array. Every element has type `T`.
5. `[x; N]` is a `[N]T` array with every element a copy of `x`. `N` is a compile-time constant.
6. A string literal `"..."` is a `[N]u8` array value holding its `N` bytes, with no terminator. Like any array it is a value, not a place: bind it to a local to take its address. `ascii::of` or `utf8::of` views it as text (§17).
7. A character literal `'a'` is an integer literal whose value is the character's byte.
8. String and character literals hold ASCII characters only. Escapes: `\n`, `\t`, `\r`, `\0`, `\\`, `\"`, `\'`, and `\xNN` for any byte.

### Places

```
place := root step*
root  := local | context field | match binding | expr.*
step  := .field | [index]
```

1. For a pointer `q`, `q.f` and `q[i]` are places rooted at a deref (§12).
2. A place **goes through a deref** if its root is `expr.*`.
3. A place is **mutable** if it goes through a deref, or its root is a `let mut` local, a `mut` context field, or a `&f` match binding (§8).
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
| struct | every field zero, if every field type has a zero value |
| `*T`, user-defined unions, `fn{C} -> R`, `&fn{C} -> R`, capability types | none |

4. Reading a variable before it is assigned is a compile error. There is no way to declare uninitialized memory.

## 12. Types

| Syntax | Meaning |
|---|---|
| `i8..i64`, `u8..u64`, `usize`, `f32`, `f64`, `bool` | primitives |
| `*T` | pointer to a `T`. Never null. |
| `[N]T` | fixed array. `N` is a compile-time constant. |
| `?T` | optional (§8). `?*T` is a nullable pointer. |
| `fn{C} -> R` | unbound function type (§5) |
| `&fn{C} -> R` | bound function type (§5, §6) |
| `type Name(G) = T` | alias |

### Pointers

1. `&p` is the address of place `p`, with type `*T`. It is allowed on any place.
2. `q.*` is the place that pointer `q` points to.
3. If `q` is a `*S` for a struct `S`, `q.f` means `q.*.f`.
4. `q + n`, with `n: usize`, points `n` elements of `T` after `q`.
5. `q[i]` means `(q + i).*`. It is not bounds-checked.
6. Exception: if `q` is a `*[N]T`, `q[i]` means `q.*[i]` (bounds-checked) and `q.len` means `N`.
7. Pointers aren't tracked. Using a pointer to memory that no longer exists, or outside its allocation, is undefined behaviour.
8. Writes through a pointer aren't checked against read-only-ness. Every place that goes through a deref is mutable (§11).

### Arrays

1. `a[i]` on an array is bounds-checked. An out-of-bounds index panics.
2. `a.len` is `N`, of type `usize`.

Slices are not built in. The standard library provides `slice::Slice(T) { ptr: ?*T, len: usize }` and bounds-checked functions on it (§17).

## 13. Builtins

1. A name starting with `@` is a compiler builtin. User code can't declare such names.
2. `@name(...)` is always a builtin call, never generic application (§9). The parentheses are required, even with no arguments.
3. Each builtin has the fixed signature below. Type arguments always come before value arguments, so the builtin's name alone says whether each argument is parsed as a type or an expression.
4. An unknown builtin, or a call with the wrong number of arguments, is a syntax error.

| Signature | Result | Meaning |
|---|---|---|
| `@size_of(T)` | `usize` | The size of `T` in bytes. |
| `@align_of(T)` | `usize` | The required alignment of `T`. A power of two. |
| `@as(T, x)` | `T` | Converts number `x` to numeric type `T`. Panics if the value isn't representable in `T`. Float to integer rounds toward zero and panics on NaN. Integer to float rounds to nearest. |
| `@trunc(T, x)` | `T` | Converts integer `x` to integer type `T`, keeping the low bits. |
| `@cast(*U, q)` | `*U` | Reinterprets pointer `q`. Unchecked. |
| `@addr(q)` | `usize` | The address of pointer `q` as an integer. |
| `@wrap_add(a, b)`, `@wrap_sub(a, b)`, `@wrap_mul(a, b)` | type of `a` | Integer arithmetic that wraps instead of panicking. `a` and `b` have the same integer type. |
| `@panic()`, `@panic("reason")` | none | Stops the program. Never returns. It ends a path for return and assignment checks. The reason must be a string literal. The runtime reports it with the panic's location, so no capability is needed. |

## 14. Memory

1. There is no static memory. `const NAME: T = e` declares a constant. `e` must be computable at compile time: literals, other consts, operators, `@size_of`, `@align_of`, and struct, union and array literals of these. `const` data is immutable and its location is unobservable: a const is a value, not a place, so `&C` is an error.
2. Locals and context fields live on the stack.
3. Memory not on the stack comes from `mem::pages`, which needs the `Mem` capability (§15), or from an allocator function over memory the caller provides. It is accessed only through pointers.
   - Allocators are byte-level: `alloc::Fn(S) = fn{ mut heap: S, mem: Bytes, new: usize, align: usize } -> ?Bytes`. The result must be aligned to `align`.
   - Typed code calls the standard library's `alloc::resize(T, S)`, which passes `count * @size_of(T)` and `@align_of(T)` and casts the result, or `alloc::new(T, S)` for one initialized `T`.
   - Pages are never freed. They live until the program ends.
4. The size of every local is known at compile time.
5. Structs, unions and arrays are values. Assignment and `return` copy them.
6. A `mut` context field is passed as a pointer. A read-only context field is passed by copy or by reference, at the compiler's choice. §3.1 makes the choice unobservable for checked arguments. A bind always copies (§4).
7. Stack size is finite. Exceeding it panics.

### Escape check

The compiler checks, within each function, that the address of a local doesn't outlive it. Nothing crosses function boundaries except through the call rule in 2.

1. A **stack pointer** to `L` is `&p` where `p` doesn't go through a deref and its root is `L`, a local or a read-only context field. `&x` for a `mut` context field `x` is not a stack pointer, because it points into the caller.
2. A value is **derived from** `L` if it is a stack pointer to `L`, or is produced from a value derived from `L` by:
   - `let` or assignment
   - a struct, union or array literal
   - pointer arithmetic or `@cast`
   - a call, whose result is derived from everything its read-only arguments are derived from. Arguments passed to `mut` fields don't count.

   Only values whose type contains a pointer carry this. `&fn` values follow §6 instead.
3. It is a compile error to:
   - `return` a value derived from any local or read-only context field of the function
   - assign a value derived from `L` to a local declared in a scope outside `L`'s
   - assign a value derived from `L` to a `mut` context field or any part of one
   - assign a value derived from `L` to a place that goes through a deref
4. Not checked: a callee storing a read-only pointer argument through its own `mut` field, and a pointer returned from a `&p` passed to a `mut` field. These remain undefined behaviour if the memory no longer exists (§12).

## 15. Entry point

```
fn main { mut io: Io, mut fs: Fs, args: Args } -> i32 { ... }
```

1. `fn main { ... }` is the entry point.
2. Every field of `main` must have a **capability type**, except a read-only field `args`. The runtime supplies them. A program declares only the ones it uses.
3. User code can't construct capability types. Current capability types: `Io` (console, §17 `io`), `Fs` (files, §17 `fs`) and `Mem` (memory beyond the stack, §17 `mem`).
4. `args: Args` holds the command-line arguments that follow the program, as bytes. `Args` is a top-level std alias for `slice::Slice(slice::Slice(u8))` (§17), so either spelling is accepted.
5. `main` may return `i32`: the program's exit code. Without a return type it exits with 0.

## 16. Open questions

1. **Dangling pointers across calls:** the escape check (§14) is intraprocedural. Would inferred per-function summaries be worth it?
2. **Read-only pointers:** `&x` on a read-only place gives a writable `*T`. Add `*mut T`?
3. **Allocator instance mismatch:** passing a different `S` instance of the same type isn't caught. Brands would close this.
4. **Method sugar:** should `x.f{...}` mean `f{ first = &x, ... }`?
5. **File = namespace:** should each file implicitly be a namespace?
6. **Imports:** some form of `use slice::Slice` to shorten long paths?
7. **Variant shorthand:** should `.variant{...}` be allowed when the expected type is known?
8. **Untagged unions:** needed for C interop? Or `@cast` only?
9. **Large stack frames:** should the compiler error or warn above a size limit? (Page allocation is now the `Mem` capability, §15.) Should pages be freeable?
10. **Loop control:** `break` and `continue` apply to the innermost loop. Are labels needed to leave an outer loop?
11. **Strings:** literals are `[N]u8` values (§11) and text is `ascii::String` or `utf8::String` (§17). Should `utf8::String` become the only text type, with `ascii` reduced to byte-level character tests? Should a literal be usable where a slice is expected without first binding it to a local?

## 17. Standard library

1. The standard library is ctxlang source (`std/*.ctx`), except for a few functions provided by the runtime (natives). It is part of every program.
2. Its namespaces are visible from user code as if declared at top level. A user declaration with the same name shadows a std one (§10).
3. It allocates only through an allocator the caller passes in (§14), and does IO only through an `Io` or `Fs` the caller passes in (§15). Only `mem::pages` takes memory from the system, through a `Mem` the caller passes in.

| Namespace | Contents |
|---|---|
| `slice` | `Slice(T)`, `from`, `of` (view an array), `empty`, `is_empty`, `at`, `get`, `set`, `sub`, `cast`, `copy`, `fill` |
| `Args` | Declared at the top level: `type Args = slice::Slice(slice::Slice(u8))`, the type of `main`'s `args` (§15). |
| `Result(T, E)` | Declared at the top level: `union Result(T, E) { ok{ value: T }, err{ error: E } }`. Namespace `result`: `is_ok`, `is_err`, `value`, `error`, `value_or`, `unwrap`, `ok_or`. |
| `fs` | `File`, `Mode` (`read`, `write`, `append`, `create`), `Error`; `open`, `read`, `write`, `close`, `size`, `remove`, and `read_all` (into memory from an allocator) and `write_all`. Every function takes `mut fs: Fs` and reports failure as a `Result(T, fs::Error)` or `?fs::Error`. Natives: `sys_open`, `sys_read`, `sys_write`, `sys_close`, `sys_size`, `sys_remove`. |
| `alloc` | `Bytes`, the allocator type `Fn(S)`, typed `resize(T, S)`, and `new(T, S)` and `free(T, S)` for one `T`: `new` returns a `?*T` holding the given `value` |
| `mem` | `pages`: at least `size` bytes of zeroed, page-aligned memory, as a `?alloc::Bytes`. Takes `mut mem: Mem`. Native: `sys_pages`. |
| `arena` | `Arena`, a bump allocator: `new`, `alloc` (an `alloc::Fn(Arena)`), `reset`, `remaining` |
| `list` | `List(T, S)`: `new`, `reserve`, `push`, `pop`, `get`, `set`, `at`, `items`, `clear`, `each`, `free` |
| `map` | `Map(K, V, S)`, a hash map that holds its key type's hash and equality functions: `new`, `len`, `has`, `get`, `at`, `put`, `remove`, `clear`, `free`, `next`, `each`. `hash_*` and `eq_*` for `i32`, `i64`, `u32`, `u64`, `usize` and byte slices; `hash_string` for `ascii::String`, with `ascii::eq`; `hash_utf8` for `utf8::String`, with `utf8::eq`. |
| `ascii` | `String { bytes: slice::Slice(u8) }`, a non-owning view of ASCII text: `from`, `of`, `empty`, `len`, `at`, `sub`, `eq`, `starts_with`, `ends_with`, `find`, `find_str`, `split_once`, `trim`, `trim_start`, `trim_end`, character tests and case, `parse_i64`, `parse_u64`, `parse_f64`, `parse_f32`, `fmt_i64`, `fmt_u64`, `fmt_f64`, `fmt_f32`. `Cursor`: a read position for lexers: `cursor`, `done`, `rest`, `peek`, `peek_at`, `bump`, `eat`, `eat_str`, `take_while`, `skip_space`. `Builder(S)`: a growable string that owns its bytes, with `push`, `push_char`, `push_i64`, `push_u64`, `push_f64`, `push_f32`. Natives: `f64_digits`, `f32_digits`, `f64_parse`, `f32_parse`. |
| `utf8` | `String { bytes: slice::Slice(u8) }`, a non-owning view of valid UTF-8 text. Offsets are in bytes, and an offset inside a character panics; a character is a `u32` code point. `from` (checks the bytes, returning `Result(String, Invalid)` with the offset of the first bad byte), `of`, `from_ascii`, `to_ascii`, `empty`, `len` (bytes), `count` (characters), `is_boundary`, `at`, `sub`, `eq`, `starts_with`, `ends_with`, `find`, `find_str`, `split_once`, `trim`, `trim_start`, `trim_end`, `encode`, `is_scalar`. Character tests and case (ASCII only). `Cursor` and `Builder(S)` as in `ascii`, by character. |
| `io` | `Stream`; `print`, `println`, `eprint`, `eprintln`, their `_utf8` forms for `utf8::String`, `newline`, `put_char`, `print_i64`, `print_u64`, `print_f64`, `print_f32`, `print_bool` and their `println_` forms (smaller number types widen to these), `read_line`. Natives: `write`, `read`. |

```
fn main { mut io: Io } {
    let hi = "hello"                                   // [5]u8
    io::println{ &io, s = ascii::of{ chars = &hi } }
    io::println_i64{ &io, n = 42 }
}
```
