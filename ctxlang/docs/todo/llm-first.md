# LLM-first checklist

What ctxlang still needs so that a model writes correct code on the first or second try. Work
through the items in order, one at a time; remove an item when its *Done when* holds, naming it
in the commit's message.

The guiding rules, in order of weight:

1. **No silent wrong answers.** A compile error costs a model one retry; a wrong result costs a
   debugging session, or ships.
2. **The safe form must be the easy form,** or code drifts to the unchecked one.
3. **What a model writes by default compiles,** or fails with an error that states the fix.
4. **Feedback is fast, complete and machine-readable.**

Evidence comes from [friction.md](friction.md) (17 agent write-ups from ctxc and the KOTOR port;
entries are cited by number, e.g. F#24) and [kotor/docs/tooling-gaps.md](../../../kotor/docs/tooling-gaps.md).

## Items

- **1. Choosing files.**
  One half-written file breaks every build that adds its directory, since a build can't add one
  file. (The other half of this item, a boundary between a library's contract and its helpers, is
  built: a folder that holds an `api.ctx` is a module, which code outside reaches only through
  that file; [spec §10, Modules](../spec.md#modules), internals.md, Modules.)
  - Details: F#5; [spec §19](../spec.md#19-build-programs).
  - *Done when:* a build can add one file.

- **2. Borrow contracts in signatures.**
  The escape check infers what a call borrows from the callee's body, so an error at a call
  depends on code the model doesn't see, and false positives push code to heap copies. A written
  contract (the `#noescape` field attribute that was put off) keeps reasoning local.
  - Details: F#2; [spec §14, Escape check](../spec.md#escape-check), [§16](../spec.md#16-open-questions).
  - *Done when:* decided: either the attribute, or a reason it isn't needed, recorded in the spec.

- **3. A formatter.**
  `ctxc fmt`: one canonical layout, so a model's edits (exact-string matching) and diffs stay
  reliable.
  - *Done when:* `ctxc fmt` is idempotent over std, ctxc and kotor.

- **4. Remaining friction.** Enum ordering and counts (F#10), `&fn` as a struct field
  (F#13), slices staying `[]mut` until freed (F#22, F#25), a `mut` argument that is a temporary
  (F#27), locking through a read-only pointer (F#28), tuples (F#29), scoped lock (F#23), array
  lengths from any folded const (F#37). Take them as they come up; each has its entry in
  friction.md.

## Not adding

Methods, macros, traits, implicit conversions and default arguments, for brevity's sake. The
explicitness is why the semantics work for a model: make the explicit forms cheap to write (puns,
`for`, indexes of any integer type) rather than hiding them.
