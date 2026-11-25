# C interop: what is left

The goal is real programs over C libraries: OpenGL or Vulkan rendering, windowing, audio.

- **Loading a library at run time**, where the capability means "it loaded".
- **Floats as text in ctxlang.** `ctxc/rt/ctxfloat.c` is the last of std's natives in C:
  shortest round-trip printing over `snprintf`, as Python's `repr`, and parsing over `strtod`,
  which a program links only if its C uses them (drive.ctx, `uses_float`). A printer with exact
  big-integer digits (Steele and White's, or Ryu's tables) and a correctly rounding parser would
  make std need no C of its own. The failed float-to-integer `@as` writes its value as text too,
  so its message would come from std as well, through the panic fn.

## Platforms

Each waiting for a target that needs it:
- **macOS on x86_64:** its `readdir` returns the old `struct dirent` unless it is called as
  `readdir$INODE64`, so `sys::DIRENT_NAME` (21, arm64's) is wrong there. A layer is per OS, not
  per architecture, so this needs a way to choose by both.
- **A port's own layer:** a build program naming a layer of its own for a platform std doesn't
  know (`build::platform{ &b, exe, dir }`), so that a port supplies `namespace os` without
  editing std.
- **Freestanding:** a target with no layer at all, where everything that takes no capability
  still works. A program supplies its own `#start` and `#panic` fns (spec §15); what's left is
  std compiling without a layer, a pages fn for function values' records past the runtime's
  first 64 KiB (std/rt.ctx, `record_pages`), and memcpy, memset and fmod, which C compilers call
  themselves.
