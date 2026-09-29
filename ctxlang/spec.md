# ctxlang: spec draft

Example: [examples/list.ctx](examples/list.ctx)

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
3. A pattern `variant{ f }` binds payload field `f` as a read-only local. A pattern may bind a subset of the fields.
4. If the scrutinee has type `*U` for a union `U`, the match goes through the pointer. In its arms, `&f` binds payload field `f` as a mutable place.
5. `&f` in a pattern is an error unless the scrutinee is a pointer.
6. If the scrutinee is `&p`, no place that overlaps `p` (§3.1) may be accessed inside an arm except through that arm's bindings. For other pointer scrutinees this isn't checked.
7. `match` is a statement.

### Optional

1. `?T` is a built-in union with variants `null` and `some{ value: T }`.
2. `null` is a value of every `?T`. An expression of type `T` converts implicitly to `?T` as `some{ value = expr }`.
3. Narrowing: in `if (x != null) { B }`, `x` has type `T` in `B`. In `if (x == null) { } else { B }`, `x` has type `T` in `B`. `x` must be a `let` local or a read-only context field. To narrow a mutable one, copy it first (`let y = x`) or `match` on it.

## 9. Generics

1. Generic parameters are types, listed in `( )` directly after a declaration's name.
2. `( )` directly after a name or `::` path, with no whitespace in between, is generic application. Everywhere else, `( )` groups an expression. Builtins are the exception (§13).
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
x = e
if (e) { } else if (e) { } else { }
while (e) { }
match (e) { ... }
return e
return
f{ ... }
```

1. Conditions and match scrutinees are always in parentheses.
2. `{` after the `)` of a condition or scrutinee, after `else`, or after `=>` begins a block. `{` after any other expression begins a call or literal.
3. Statements are separated by newlines or `;`. A postfix `{`, `[` or `(` must be on the same line as the expression before it.
4. Every block is a scope. A `let` is visible from its declaration to the end of its block.
5. In `x = e`, `x` must be a mutable place.
6. An expression statement must be a call or a builtin call. Its result is discarded.
7. `return` without a value is only allowed in a function with no `-> R`. In a function with `-> R`, every path must end in `return e` or `@trap()`.

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

1. Arithmetic applies to two operands of the same numeric type. There are no implicit numeric conversions. Use `@as` or `@trunc` (§13).
2. Integer `+ - *` trap on overflow. `/` and `%` trap on a zero divisor. Use `@wrap_*` (§13) for wrapping arithmetic.
3. `==` and `!=` work on numbers, `bool` and pointers (by address), and on `?T` against `null`. Other types have no built-in equality.
4. `and`, `or` and `not` take and give `bool`. Conditions must be `bool`.

### Literals

1. An integer literal (`42`) has an integer type that is inferred from every use within the enclosing function body, including uses of locals it initializes. If no use fixes it, it is `i32`.
2. A float literal (`1.5`, `2e3`) is inferred the same way among float types, and defaults to `f64`.
3. `true` and `false` are the `bool` values. `null` is described in §8.
4. `[a, b, c]` is a `[3]T` array. Every element has type `T`.
5. `[x; N]` is a `[N]T` array with every element a copy of `x`. `N` is a compile-time constant.

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

1. `let x: T` without an initializer: `x` must be assigned exactly once on every path before it is read.
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

1. `a[i]` on an array is bounds-checked. An out-of-bounds index traps.
2. `a.len` is `N`, of type `usize`.

Slices are not built in. The standard library provides `slice::Slice(T) { ptr: ?*T, len: usize }` and bounds-checked functions on it.

## 13. Builtins

1. A name starting with `@` is a compiler builtin. User code can't declare such names.
2. Arguments are in `( )`. They are types or expressions. `@name(...)` is always a builtin call, never generic application (§9).

- `@size_of(T) -> usize`
- `@as(T, x) -> T`: converts a number to numeric type `T`. Traps if the value isn't representable in `T`. Float to integer rounds toward zero and traps on NaN. Integer to float rounds to nearest.
- `@trunc(T, x) -> T`: converts an integer to integer type `T`, keeping the low bits.
- `@align_of(T) -> usize`: the required alignment of `T`. A power of two.
- `@addr(q) -> usize`: the address of pointer `q` as an integer.
- `@wrap_add(a, b)`, `@wrap_sub(a, b)`, `@wrap_mul(a, b)`: integer arithmetic that wraps instead of trapping.
- `@cast(*U, q) -> *U`: reinterprets pointer `q`. Unchecked.
- `@trap()`: stops the program. Never returns. It ends a path for return and assignment checks.

## 14. Memory

1. There is no static memory. `const NAME: T = e` declares a constant. `e` must be computable at compile time: literals, other consts, operators, `@size_of`, `@align_of`, and struct, union and array literals of these. `const` data is immutable and its location is unobservable: a const is a value, not a place, so `&C` is an error.
2. Locals and context fields live on the stack.
3. Memory not on the stack is obtained only by calling an allocator function, and is accessed only through pointers.
   - Allocators are byte-level: `alloc::Fn(S) = fn{ mut heap: S, mem: Bytes, new: usize, align: usize } -> ?Bytes`. The result must be aligned to `align`.
   - Typed code calls the standard library's `alloc::resize(T, S)`, which passes `count * @size_of(T)` and `@align_of(T)` and casts the result.
4. The size of every local is known at compile time.
5. Structs, unions and arrays are values. Assignment and `return` copy them.
6. A `mut` context field is passed as a pointer. A read-only context field is passed by copy or by reference, at the compiler's choice. §3.1 makes the choice unobservable for checked arguments. A bind always copies (§4).
7. Stack size is finite. Exceeding it traps.

## 15. Entry point

1. `fn main { ... }` is the entry point.
2. Every field of `main` must have a **capability type**. The runtime supplies them.
3. User code can't construct capability types. Current capability types: `Io`.

## 16. Open questions

1. **Dangling pointers:** add a lint for returning or storing `&local`?
2. **Read-only pointers:** `&x` on a read-only place gives a writable `*T`. Add `*mut T`?
3. **Allocator instance mismatch:** passing a different `S` instance of the same type isn't caught. Brands would close this.
4. **Method sugar:** should `x.f{...}` mean `f{ first = &x, ... }`?
5. **File = namespace:** should each file implicitly be a namespace?
6. **Imports:** some form of `use slice::Slice` to shorten long paths?
7. **Expressions:** should `if` and `match` be expressions?
8. **Variant shorthand:** should `.variant{...}` be allowed when the expected type is known?
9. **Untagged unions:** needed for C interop? Or `@cast` only?
10. **Large stack frames:** should the compiler error or warn above a size limit? Should `main` receive an `Os` capability for page allocation?
11. **Loop control:** add `break` and `continue`?
12. **Strings:** literal syntax and type (`Slice(u8)`? a `const` byte array?).
