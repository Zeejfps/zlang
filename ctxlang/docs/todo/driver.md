# The driver: what is left

Each only if it gets in the way (ctxc/drive.ctx):
- The front end runs on every `ctxc run`, changed or not: 1.9 s for 99K lines, now the largest
  part of a rebuild. A hash of the sources and of ctxc itself could skip it too; checking and
  lowering only the files that changed is a bigger change.
- A unit's C holds the declarations its functions use, so a big program's units hold about a
  third more C than one file does. The layouts are checked (`_Static_assert`) only in main's.
- Inserting a line moves the positions after it, so every unit of that file is recompiled, though
  only one function changed. Positions relative to their function's first line would keep them.
- A file's units are its functions by a hash of their names; files smaller than a unit share one
  with the next files of their directory, so one that grows past a boundary moves the files after
  it into other units.
- Copies are chosen by size alone, counted in the IR rather than in what C would inline. A big
  function called once from another unit, as a generated ECS runner calls its system, still
  isn't inlined there; grouping functions into units by who calls whom would let it be.
- A file reached twice is found by its absolute path, without looking at links, so a file reached
  through a symbolic link or a junction and directly is compiled twice.
- A C compiler replaced in place by another version isn't noticed: removing build/run starts
  afresh. Nor are the files a killed build leaves, `NAME.N.c` and the like, ever removed.
- `ctxc build`, `ir` and `decls` need std's files listed on the command line; only `run` and `exe`
  find them.
