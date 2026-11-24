# Language server: what is left

`ctxc lsp` speaks LSP (JSON-RPC over stdin and stdout) and answers from the checker's side
tables. It is a command of ctxc, in `ctxc/lsp.ctx` and files beside it, so the front end, the
driver and std's files are already there and the editor finds the server wherever it finds ctxc.

The front end was built for this: `check::new{ files, .. }` and `check::program` take source text
(so unsaved buffers work), recover from errors in the lexer, parser and checker, keep comments on
the side (`lexer::Lexed.comments`), and record results in side tables by node key, so parsed trees
stay read-only and std's needn't be reparsed after an edit: its trees stay in the arena below a
`mark`, and each check `restore`s to it.

| Record | In `check::Checker` | Serves |
|---|---|---|
| each name use → what it names | `uses` (a `Ref`), `refs` (a `PathRef`), `local_of`; a local's span is `Var.at`, a declaration's its `syntax::Decl` | go to definition, references, rename, semantic tokens |
| a field use → its field | not kept: found from the receiver's type in `expr_ty` and the field's name | go to definition, hover |
| each expression's type | `expr_ty`; a narrowed field's own `?T` in `narrowed` | hover, inlay hints |
| each declaration: kind, name, namespace | `decls` (`Decl.kind`, `name`, `qual`, `syn`) | document and workspace symbols, hover |
| what a `..` supplies | `forwards`, `filled` | hover on `..` |
| where each local's name is in scope | `lives` (a `Live`: the local, from where its name takes effect to where its scope ends; the latest `from` wins), and its type in `Var.ty`, narrowed for a narrowed view | completion of names |
| the fields each `{` takes: a call's, generic arguments inferred, or a literal's type's | `braces` (recorded by `supplied`, so half-typed braces have them too) | completion of field names, signature help |

1. **The server:** reading messages (a `Content-Length` header, then that many bytes, by
   `io::read` in a loop), writing them (`io::write_bytes`, then `io::flush`), and JSON, by the
   parser and printer of `examples/json` moved into `ctxc/`.
2. **Features, in order:** diagnostics on open and change (debounced), go to definition, hover
   (type and signature), document symbols, completion (names in scope, fields after `.`, context
   fields inside `{`), references, rename, workspace symbols, semantic tokens, signature help,
   inlay hints for inferred `let` types.
3. **Doc comments,** for hover: their syntax is a spec decision of its own, still to make.
4. **Editor-query fixtures:** files that mark positions (`/*^def*/`, `/*^hover*/`) and state the
   expected answer, read by the suite's runner, which covers the semantic model without a client.

Design notes:
- **Threads.** One thread reads stdin and queues messages; the main thread takes them, and waits
  with `condition::wait_for` to debounce a run of changes into one check (std/thread.ctx).
- **Positions.** Spans are byte offsets; the server converts to whatever the client negotiated:
  UTF-8 if it accepts `positionEncoding`, UTF-16 otherwise.
- **Workspace.** A program is a directory of `.ctx` files plus std (§10). An open file joins the
  program in its directory. Buffers the editor holds replace the text on disk. A directory with a
  build.ctx is checked with the files its build program gives each executable, generated ones
  included, which the server learns by running it as the driver does (drive.ctx); it runs again
  when build.ctx or a file under a `#build::sources` directory is saved.
- **Speed.** On every edit the server re-lexes and reparses the files that changed and rechecks
  the whole program: about 100 ms for ctxc's own source. Only if a profile says otherwise: skip
  unchanged function bodies, or check only up to the cursor for completion.
- **Consts and converted literals** have their errors only in a program without other errors
  ([comptime.md](comptime.md)); the server reports what the checker reports.

*Done when:* VS Code, with a minimal client extension, shows diagnostics while you type, and go to
definition, hover and completion work on `ctxc/` itself. The editor-query fixtures pass.
