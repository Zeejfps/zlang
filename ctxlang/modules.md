# Modules: design

Status: **design**. Nothing here is built. It replaces LLM-FIRST 2.1's file-private declarations
with a boundary of another kind: a folder that holds an `api.ctx` is a **module**, and code outside
it reaches only what that file declares.

## Why

Every name in a program is visible everywhere (§1, rule 2), and a namespace is open: any file may add
to it (§10, rule 4). Nothing tells a function that callers depend on from a helper that one file
uses, so:

- **Changing a function's signature can break code anywhere** (FRICTION #14). An agent that changes a
  helper finds its callers as build errors, in files other agents own. To change anything safely, it
  has to grep the whole program first.
- **There is nowhere to read a library's contract.** An agent using `gff` reads its implementation to
  learn which functions are meant for callers, which types it can construct and which errors come
  back. The function results that `-> !T` infers (§8, Errors, rule 5) make this worse: what a function
  fails with is known to the compiler and to no reader.
- **A subsystem can't keep state of its own** (FRICTION #5). Every cache goes in `World`, the type
  every agent edits.
- **Parallel agents coordinate helper names by message** (FRICTION #5), since a namespace's names are
  unique across all its files.

Making declarations private one at a time (a `private` attribute, a `private` nested namespace, or
file-private names) addresses the last two. But it doesn't give a library a contract, and it hides
helpers that other code could have reused. Being public by default is worth keeping: an agent that
finds a helper can call it instead of writing it again. A boundary should be drawn on purpose, where
a contract is wanted, and everywhere else names stay public.

## What other languages learned

- **C** has headers because files are compiled separately. The header is the only thing a caller
  sees, but nothing checks it against the implementation beyond the link, and `static` is the only
  privacy.
- **OCaml** pairs a `.ml` with an optional `.mli`, the module's signature. The compiler checks the
  implementation against it, an abstract type in it hides a type's representation, and anything it
  leaves out is private. A module without a `.mli` exposes everything.
- **Ada** splits every package into a spec and a body. The spec is the contract and can't drift from
  the body, but every package needs both.
- **Go** makes a folder a package, and an initial capital makes a name exported. An `internal/`
  folder is visible only to the tree rooted at its parent. Most of Go's friction with packages, such
  as the ban on import cycles, comes from compiling each package separately.
- **Rust** marks each item `pub` or not. The contract is spread through the implementation, and
  `pub use` re-exports a name, possibly under another name.

ctxc compiles the whole program at once, so a contract file isn't needed to build anything: like
OCaml's `.mli`, it exists only as a contract, which the compiler checks in both directions. It is
optional, as `.mli` is. Without one, nothing changes.

## Shape

```
lib/formats/
    gff/
        api.ctx          // this folder is a module
        read.ctx
        write.ctx
        tests.ctx        // inside: sees everything
    tpc/
        api.ctx
        decode.ctx
    util.ctx             // outside gff and tpc: sees only their api.ctx
```

```
// lib/formats/gff/api.ctx
namespace gff {
    type Gff                                         // opaque: held and passed, never looked into
    struct Field { label: []u8, kind: Kind }
    enum Kind { byte, word, dword, string }

    error bad_magic
    error truncated{ at: usize }

    fn read { bytes: []u8 } -> error(bad_magic, truncated)!Gff
    fn field { g: *Gff, label: []u8 } -> ?Field
}

// lib/formats/gff/read.ctx
namespace gff {
    struct Gff { header: Header, fields: []Field }   // the opaque type's body
    fn read { bytes: []u8 } -> error(bad_magic, truncated)!Gff { ... }
    fn parse_header { bytes: []u8 } -> !Header { ... }   // not in the api: inside only
}
```

`api.ctx` is ctxlang: namespace blocks and declarations. It is the one file where a function has no
body and a type has no fields. No keyword marks it; its name does.

## Modules

1. A folder that holds a file named `api.ctx` is a module. Its **inside** is every source file in the
   folder and in its subfolders, at any depth; everything else is **outside**, sibling and parent
   folders included. A file's place on disk, not the build that adds it (§19, rule 5), decides which
   modules it is inside.
2. Code inside a module sees every declaration in it. Code outside sees only what its `api.ctx`
   declares, and what that file exposes of modules nested in it (Re-exports).
3. A declaration that is complete without a body is declared in `api.ctx` alone, and the inside uses
   it: an `error`, an `enum`, a `struct` with its fields, a `union`, a `const`, a `type` alias, a
   `capability` with only function fields. Three have a second half inside:
   - `fn name(G) { ... } -> R`, without a body, is a function the inside defines with exactly that
     signature: generic parameters, context fields with their `mut`, and result.
   - `type Name(G)`, with no `=`, is an **opaque** type the inside defines as a struct, a union or an
     enum. Outside, it can be held, copied, passed and returned, but not constructed, and its fields
     and variants can't be named. ctxc compiles the whole program, so its size is known and it is
     passed by value as any other type is.
   - `capability Name`, or one with its function fields alone, is a capability whose `static` and
     `extern` fields (§15, rules 12 and 13) the inside adds, in a declaration of the same capability
     that repeats every field the api's has (rule 7).

   Each half without the other is an error, as is a definition that doesn't match.
4. **Nothing leaks through a signature.** A type or an error that a declaration in `api.ctx` names, in
   a function's signature, a struct's fields or a set alias, is in the api, in full or opaque. The
   error names each one missing.
5. **A function in `api.ctx` declares its error set.** Its result is `E!T` (§8, Errors, rule 14),
   never `!T`, so every caller can read what it fails with, and the inside can't add an error without
   changing the contract. Inside the module, results are inferred as before.
6. A `#test` fn follows rule 2 as any code does. One inside the folder, in a subfolder kept for
   tests included, tests the module as a white box; one outside tests it as a black box, through the
   api alone. Nothing outside a module reaches inside it, tests included:

   ```
   lib/formats/gff/
       api.ctx
       read.ctx
       tests/               // inside gff: tests parse_header and every other helper
           read_test.ctx
           data/            // fixtures, found with test::dir (§20, rule 12)
   tests/
       formats/
           gff_roundtrip.ctx  // outside: tests what gff's api promises, as a caller would
   ```

   A test that uses a module's internals breaks when they change, and the boundary is there so that
   such a change breaks only code inside the module. A white-box test is part of the implementation,
   kept where the agent changing the internals already works. A test outside that needs a hidden
   name shows the name is either part of the contract, and goes in `api.ctx`, or a module of its own
   nested inside, with an api the tests use.

   What isn't here: a `#test` fn that sees past every boundary, since a test is a fn other code may
   call (§20, rule 1) and could hand a hidden function on, and a list in `api.ctx` of outside folders
   that may see inside, which makes a module's guarantee depend on files it doesn't own.
7. **A module's state is in a capability whose statics only it reaches.** A capability reaches a
   function only through its context, passed down from `main` (§15, rules 1 and 2), so one that an
   api function takes is named by rule 4 in the api, and `main` names it too. The api declares it
   without its `static` and `extern` fields, and the inside declares it with them:

   ```
   // lib/formats/gff/api.ctx
   namespace gff {
       capability Cache                             // what callers see: one without fields
       fn read_cached { mut cache: Cache, bytes: []u8 } -> error(bad_magic, truncated)!*Gff
   }

   // lib/formats/gff/cache.ctx
   namespace gff {
       capability Cache { static table: Table }    // the second half: its statics
   }

   // main.ctx
   fn main { mut io: Io, mut fs: Fs, mut gff_cache: gff::Cache } -> i32 { ... }
   ```

   A capability whose only fields are statics and C variables is one without fields (§15, rule 1),
   which is what code outside sees, and passes on as it passes an `Io`. A static or a C variable is
   reached only in a function declared directly in its capability's namespace (§15, rules 12 and
   13) and inside its module, so another module that adds to the namespace doesn't reach it. A
   subsystem's cache lives there, not in `World`.
8. A hidden name is in its module's scope, not its namespace's. Two names clash only where both are
   visible: a hidden `gff::put_row` in one module and a hidden `gff::put_row` in another are two
   functions, and code inside either module sees its own. A hidden name that clashes with a name
   visible at its declaration is an error, as two declarations of one name are now (§10, rule 4).
9. Namespaces stay separate from folders. A module may declare several namespaces in `api.ctx`, and
   several modules may add to one namespace, as `formats::gff` and `formats::tpc` from two modules.
   Which module declares a name is answered by ctxc (Tooling), not by a convention of paths.
10. Calling, constructing or naming something hidden is an error that names the boundary:
    ``gff::parse_header` is inside module `lib/formats/gff`, whose `api.ctx` doesn't declare it``.
11. Privacy is of names, not values. A function value the inside hands out (§5) can be called by
    whoever holds it, as in Rust and Go.
12. A program of one file (`ctxc run file.ctx`) is in no folder that a build reads, and has no
    modules.

## Re-exports

A re-export makes a name declared by a nested module visible past its parent's boundary. It never
makes a new name: `gff::read` is `gff::read` at every level, so a name always means one thing.

```
lib/formats/
    api.ctx              // formats is a module, for internals gff and tpc share
    shared.ctx           // inside formats: gff and tpc see it, nothing outside does
    gff/
        api.ctx
    tpc/
        api.ctx
```

1. **Restating** a declaration re-exports it:

   ```
   // lib/formats/api.ctx
   namespace gff {
       type Gff                                     // narrowed: opaque past this boundary
       error bad_magic
       error truncated{ at: usize }
       fn read { bytes: []u8 } -> error(bad_magic, truncated)!Gff
   }
   ```

   A declaration in `api.ctx` whose name a nested module's api declares is that declaration, not a
   new one. A restatement may hide a type's inside, never change a declaration: a struct, union or
   enum the nested api declares in full may be restated opaque, `type Gff`, and is then opaque past
   this boundary and in full inside it; every other restatement matches exactly. So a name that is
   visible means one thing, with one type, at every level it reaches, and a restatement says only
   what an `api.ctx` could say of a declaration of its own. The outer api is then the whole contract,
   with its signatures, in one file.

   What a restatement can't do, and why:

   - **Show some of a struct's fields.** Code outside couldn't construct one, since a literal
     supplies every field (§7), and could break, by writing the fields it sees, what holds between
     them and the ones it doesn't. An opaque type with functions that read and set what callers need
     says the same, with names.
   - **Hide some of an enum's or a union's variants.** Code outside would hold values it can't name
     and match with `else`: an enum that may gain variants, which would be a property of enums
     everywhere, not of modules. ctxlang breaks every exhaustive match when a case is added, on
     purpose (§8, Errors, rule 10).
   - **Widen a function's error set.** `gff::read` would have one type inside `formats` and another
     outside it, so `let f = gff::read` would differ by where it is written, and converting between
     them would need a thunk. `gff/api.ctx` is inside `formats`: a wider contract is declared there.
   - **Change `mut`, narrow a set, or change anything else of a signature.** It is the declaration.
   - **Restate a const without its value.** A const's value is used while compiling, as an array's
     length or in folding. A value kept from callers is a function's result.
2. **`expose "path"`** re-exports all of a nested module's api, as that api declares it:

   ```
   // lib/formats/api.ctx
   expose "gff"
   expose "tpc"
   ```

   The path is a string, relative to the folder of this `api.ctx`, so that a folder named as no
   ctxlang name can be (`2da`) is still reachable. It names a module whose folder is directly inside
   this one, or inside a folder in between that isn't a module. `expose` is a keyword only where a
   declaration begins in an `api.ctx`, as `error` is only before a name (§1, rule 4).
3. **One boundary at a time.** An `api.ctx` re-exports only what code inside its module sees: a
   nested module's api, with what that api re-exports in turn. A name in `formats/gff/chunks/`
   crosses `formats` only if `gff/api.ctx` re-exports it first.
4. A module is either restated from or exposed, not both: a restatement beside an `expose` of the
   same module is an error.
5. The leak rule (Modules, rule 4) holds for re-exports: restating `read` without `Gff`,
   `bad_magic` and `truncated` is an error that names them.
6. A folder without an `api.ctx` is no boundary. Nested modules under a plain folder, such as `gff/`
   and `tpc/` under a `formats/` that is only a folder, are visible to everyone through their own
   apis.

What isn't here, and why:

- **A list of names** (`export gff::{ read, field, Gff }`). The outer api would show names without
  their signatures, which is the thing an api file is for, and it couldn't narrow a type to opaque.
- **Renaming** (`pub use gff::read as read_gff`). Two names for one function is two names to learn
  and to search for.
- **A nested module that declares itself visible past its parent.** The parent decides its own
  surface.
- **`expose` with exceptions.** Restating is the way to expose part of a module.
- **`export` as the keyword.** Models know `export` from TypeScript, together with the forms this
  design rejects: `export fn`, `export { a, b }`, `export { a as b }`. A model shown `export` in an
  `api.ctx` would write them, and each is an error; an unfamiliar word sends it to the spec. Everything
  in `api.ctx` is public already, so the file is the export, and the directive does something else:
  it passes a nested module's api out through this boundary. In a language this close to C, "export"
  also means making a symbol visible to the linker, which `#c::export` does (todo.md).

## Tooling

- `ctxc check` reports every module rule above with the rest of the program's errors (§21).
- ctxc answers where a name is declared: the module and the file, for a name in any namespace (rule 9).
- ctxc writes a first `api.ctx` for a folder, from the declarations its files have that code outside
  uses, with each function's set as inferred today: the starting point for a contract, not one kept
  up to date.

## How it addresses the friction

| | What changes |
|---|---|
| FRICTION #14, a changed signature breaks unowned callers | A hidden function's callers are all inside its module. A changed contract is a changed `api.ctx`, visible in a diff, and an edit an agent can be told to ask before making. |
| No contract to read | One file per module, with every error set written out (rule 5). |
| FRICTION #5, caches in `World` | A capability whose statics only its module reaches (rule 7). |
| FRICTION #5, names coordinated by message | Hidden names clash only where both are visible (rule 8): an agent working in its own module names its helpers freely. |
| Duplicated helpers | Names are public until a module hides them, so a helper found can be reused. |

FRICTION #5's other half, a build that can add one file and not its whole folder, is a matter of
building, not of visibility, and stays LLM-FIRST 2.1's.
