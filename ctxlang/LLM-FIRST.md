# LLM-first checklist

What ctxlang still needs so that a model writes correct code on the first or second try. Work
through the items in order, one at a time; tick an item when its *Done when* holds, and note the
commit beside it.

The guiding rules, in order of weight:

1. **No silent wrong answers.** A compile error costs a model one retry; a wrong result costs a
   debugging session, or ships.
2. **The safe form must be the easy form,** or code drifts to the unchecked one.
3. **What a model writes by default compiles,** or fails with an error that states the fix.
4. **Feedback is fast, complete and machine-readable.**

Evidence comes from [FRICTION.md](FRICTION.md) (17 agent write-ups from ctxc and the KOTOR port;
entries are cited by number, e.g. F#24) and [kotor/docs/tooling-gaps.md](../kotor/docs/tooling-gaps.md).

## 1. A reference a model can trust

- [x] **1.1 Move the quick reference into ctxlang.**
  Agents learned the language from `kotor/docs/ctxlang-quickref.md`, which lived in the game,
  not the language; it is now [quickref.md](quickref.md), with the game's own parts in
  kotor/AGENTS.md ("ctxlang in this game"). No model has ctxlang in its training data: this
  page is its first source of truth. Move it to `ctxlang/`, keep it short, name the spec
  sections, and list the common mistakes with their fixes.
  - *Done when:* it lives in ctxlang, kotor's AGENTS.md points to it, and it's current with this checklist's changes.

- [ ] **1.2 Every code block in the spec and the reference compiles.**
  The spec has drifted: hex literals work but aren't in §11 (F#16), and §14's folded consts
  aren't what the folder takes (F#37). A test extracts each block (marked as a whole program,
  a fragment, or an expected error) and checks it with ctxc.
  - *Done when:* the test runs in the suite and every block passes or is marked as an error example.

## 2. Next tier

- [ ] **2.1 Modules, and choosing files.**
  A directory is one flat namespace: nothing tells a library's contract from its helpers, a changed
  signature breaks callers nobody on the task owns, parallel agents agree on helper names by
  message, and a subsystem's state goes in `World`. In place of file-private declarations, a folder
  that holds an `api.ctx` is a module, which code outside reaches only through that file
  ([modules.md](modules.md)). Apart from that, one half-written file breaks every build that adds
  its directory.
  - Details: F#5, F#14; [modules.md](modules.md); [spec §10](spec.md#10-namespaces), [§19](spec.md#19-build-programs).
  - *Done when:* modules.md is built, and a build can add one file.

- [ ] **2.2 Borrow contracts in signatures.**
  The escape check infers what a call borrows from the callee's body, so an error at a call
  depends on code the model doesn't see, and false positives push code to heap copies. A written
  contract (the `#noescape` field attribute that was put off) keeps reasoning local.
  - Details: F#2; [spec §14, Escape check](spec.md#escape-check), [§16](spec.md#16-open-questions).
  - *Done when:* decided: either the attribute, or a reason it isn't needed, recorded in the spec.

- [ ] **2.3 A formatter.**
  `ctxc fmt`: one canonical layout, so a model's edits (exact-string matching) and diffs stay
  reliable.
  - *Done when:* `ctxc fmt` is idempotent over std, ctxc and kotor.

- [ ] **2.4 Remaining friction.** Enum ordering and counts (F#10), `&fn` as a struct field
  (F#13), slices staying `[]mut` until freed (F#22, F#25), a `mut` argument that is a temporary
  (F#27), locking through a read-only pointer (F#28), tuples (F#29), scoped lock (F#23), hex
  literals in the spec (F#16), array lengths from any folded const (F#37). Take them as they
  come up; each has its entry in FRICTION.md.

## Not adding

Methods, macros, traits, implicit conversions and default arguments, for brevity's sake. The
explicitness is why the semantics work for a model: make the explicit forms cheap to write (puns,
`for`, indexes of any integer type) rather than hiding them.
