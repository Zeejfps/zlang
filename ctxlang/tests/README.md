# The test suite

ctxc's tests are files under [cases/](cases): each case is a program, or a directory with one, that
states what is expected of it. A runner written in ctxlang ([tools/suite](../tools/suite)) builds
each one with ctxc for the current source, runs it, and checks every statement. `#test` fns
(spec §20) test a program from inside; these test the compiler from outside, where a compile
error and a panic can be seen.

The cases are also examples: each is a program that compiles as it stands, or says exactly which
error it has and where.

## Running

From the repository's root (in Git Bash on Windows):

```
kotor/tools/ctxc run ctxlang/tools/suite                         every case
kotor/tools/ctxc run ctxlang/tools/suite -- Safety               those whose names contain `Safety`
kotor/tools/ctxc run ctxlang/tools/suite -- Basics/shadowing     one case
kotor/tools/ctxc run ctxlang/tools/suite -- --list Fmt           lists them, and runs none
kotor/tools/ctxc run ctxlang/tools/suite -- -v --fresh Fmt       every case's line, none from the cache
```

`--jobs N` sets how many cases run at once (the processors, by default), `--cases DIR` runs
another directory's cases, and `--corpus OUT` runs nothing: it writes every case's program to OUT,
each once, for the recovery test (tools/recover.py). A case's name is its path under `cases/` without `.ctx`:
`Safety/split_borrows/03`.

The runner builds ctxc first, from `bootstrap/` and then from `ctxc/`'s current source, so a
change to the compiler or to std is tested by the next run. Everything it writes is under
`build/suite`.

A failure is a line as `ctxc test` prints one, `FILE:LINE: fail: NAME: WHAT`, where FILE:LINE is
the statement that didn't hold, with what was expected and what came under it:

```
G:/Dev/zlang/ctxlang/tests/cases/Basics/arith_and_loops.ctx:18: fail: Basics/arith_and_loops: stdout differs at its line 2
  expected line: | 450
  actual line:   | 45
  actual, whole:
    | 6765
    | 45
    | -3
    | -1
    | 3.0
    | true
interp: 685 programs the same, 99 it cannot run, 2 off
cases: 2446 run, 2441 passed (0 from the cache), 1 failed, 4 skipped, 0 not selected
```

The exit code is 0 only if every selected case passed. These are failures, never passes:

- a case that states no expectation, or whose directives don't parse;
- a filter that selects no case, and a cases directory without cases;
- a file under `cases/` that is no case;
- a case whose process ends without a result (the runner's own crash), with what it wrote;
- a program the interpreter can't run, unless the case says so.

A case that doesn't run on this platform (`only:`) or lacks a tool (`needs:`) is skipped: it is
printed, as `FILE:1: skip: NAME: WHY`, and counted.

A case that passed isn't run again until something it depends on changes: ctxc's source, std,
the runtime, the C compiler, the runner, or the case's own files, all by hash. The summary says
how many passes came from the cache, and `--fresh` runs every selected case. A case that names
files outside itself (`{home}`, `{repo}`) is never cached.

## What the runner does with a program

As `tools/toolchain.py` did for the Python tests this suite replaces:

1. `ctxc build OUT.c STD... -- FILE...` in the case's directory, with std's files for this
   platform's layer. If ctxc reports errors, they are the result.
2. The C is compiled with `gcc`, `cc` or `clang`, the first on PATH (`zig cc` with `CTX_CC=zig`),
   with `-std=gnu11 -O1 -w -fwrapv -fno-optimize-sibling-calls -fno-strict-aliasing`, the
   runtime's objects, a 256 MiB stack, and the program's name `program`. The executable is cached
   by a hash of its C.
3. It runs, with `CTX_STACK` 16 MiB unless the case says otherwise, for at most 600 s. A panic is
   exit code 134 with `FILE:LINE:COL: panic: MESSAGE` as standard error's last line.
4. `ctxc interp` runs the same program, a second implementation: its standard output, standard
   error and exit code must be the compiled program's (a panic without a position names the
   program, `program` or the file's stem; a trap is 132 both ways).

In every text the runner compares, a run of `../` before `std/` is dropped, so a position in
std reads `std/list.ctx:60:9` wherever the case is.

## A case of one file

`NAME.ctx` is the program. Its expectations are comment lines that start with `//#`
(directives), each alone on its line, by convention after the program, and `//~` markers at the
ends of its lines.

```
// A defer's body is written at each exit.

fn run { mut io: Io, a: i32 } {
    defer _ = @fmt(&io, "{}\n", a * a ifoverflow -1)
    if a > 0 { return }
    _ = @fmt(&io, "body\n")
}
fn main { mut io: Io } {
    run{ &io, a = 70000 }
    run{ &io, a = 0 }
}

//# stdout:
//| -1
//| body
//| 0
```

```
fn main { mut io: Io } { let x: u8 = 300 }  //~ error at 38: literal 300 does not fit in u8
```

### Markers

- `//~ error at COL: MESSAGE` at the end of a line: ctxc reports MESSAGE at that line and
  column. The program's markers, in the order they are written, are **all** of ctxc's errors, in
  the order it reports them: the runner compares ctxc's whole standard error with a line
  `FILE:LINE:COL: error: MESSAGE` for each marker. A line with several errors has several
  markers. A program with an error marker isn't run.
- `//~ panic at COL: MESSAGE` at the end of a line: the program panics there, so it exits with
  134 and standard error's last line is `FILE:LINE:COL: panic: MESSAGE`. What it wrote before is
  still compared (`stdout:`, `stderr:`).

- `//~ note at COL: MESSAGE` after an error's marker, on the same line: the error has that
  note (spec §21, rule 8), at COL of the marker's own line, or with `at -N:COL` or `at +N:COL`
  at the line N above or below it, so that the marker moves with the lines it is about. An
  error's notes are stated after it in ctxc's order, and the runner expects a line `  FILE:LINE:COL:
  note: MESSAGE` under the error's for each: an error with a note the case doesn't state fails, as
  does a note that isn't there. A note in another file is stated with `errors:`.

```
fn far {} -> *i32 {
    let v: i32 = 1
    return &v  //~ error at 5: returned value holds the address of local `v` //~ note at -1:5: `v` is declared here
}
```

A marker's message runs to the end of the line, or to the next `//~`; spaces at its ends don't
count.

### Directives

A directive is `//# KEY: VALUE`, or `//# KEY:` with a block after it: lines that start with
`//| `, each a line of the text (`//|` alone is an empty line). The text ends with a line break
after each line.

| Directive | Meaning |
|---|---|
| `//# stdout:` + block | Standard output, whole. Without it, standard output must be empty. |
| `//# stderr:` + block | Standard error, whole, without the panic's line. Without it, it must be empty. |
| `//# exit: N` | The exit code. Without it: 0, or 134 for a program that states a panic. |
| `//# panic: LINE` | Standard error's last line, whole, with exit code 134: for a panic that a marker can't state, as one in std (`std/utf8.ctx:50:46: panic: ...`), without a position (`program: panic: stack overflow`) or in a task. |
| `//# errors:` + block | ctxc's standard error, whole: for errors that markers can't state, as a message of several lines, a position in another file, or an order that isn't the lines'. |
| `//# compiles` | The program builds (ctxc, then the C compiler); it isn't run. |
| `//# args: WORD...` | The program's arguments. |
| `//# stdin:` + block | Its standard input. Without it, standard input is empty. |
| `//# env: NAME=VALUE` | An environment entry, for ctxc and for the program. May be repeated. |
| `//# stack: BYTES` | `CTX_STACK` for the run. |
| `//# timeout: SECONDS` | How long the program, and the interpreter, may run. |
| `//# interp: cannot run` | `ctxc interp` must refuse the program (`ctxc interp: REASON`, exit code 1), as it does one that needs files, other programs or an extern fn it doesn't emulate. |
| `//# interp: off: REASON` | The program isn't run in the interpreter. |
| `//# only: PLATFORM...: REASON` | The case runs only on those platforms: `windows`, `linux`, `macos`, `posix` (the last two together). Elsewhere it is skipped. |
| `//# needs: TOOL...` | The case is skipped unless each tool is on PATH (`ar`). |

Rules:

1. **A case states an expectation,** or it fails: at least one of a marker, `stdout:`,
   `stderr:`, `exit:`, `panic:`, `errors:` or `compiles`. A program that prints nothing and
   returns 0 says `//# exit: 0`.
2. **Everything is compared whole.** A program's errors are all of ctxc's; its standard output
   and standard error are every byte. What a case doesn't state must be empty or 0.
3. **Other forms of an expected text.** `stdout has:` + block passes if the output contains the
   block's text, `stdout lacks:` if it doesn't, and `stdout any` (no colon, no block) compares
   nothing; `has` and `lacks` may be given more than once, and `stderr` takes the same forms.
   The text of a `has` or a `lacks` is a fragment: the block without its last line break, so
   one line of block finds text in the middle of a line (end the block with `//|` to find the
   line's break too). Use them where the whole text isn't the case's subject, and say why in a
   comment.
4. **`escaped`** after a block's key (`//# stdout escaped:`) reads the block with escapes: `\\`,
   `\n`, `\r`, `\t`, `\xNN`, and a `\` at a line's end, which takes that line's break away (so
   a text without a final line break ends in `\`). Use it for bytes a comment can't hold and
   for spaces at a line's end (`\x20`).
5. **Wildcards** in any expected text, a marker's message included: `{n}` is one or more
   digits, `{hex}` one or more hexadecimal digits (lower case), and `{any}` any text up to the
   line's end. For what differs from machine to machine, as a recursion's depth or a hash.
6. **Placeholders** in a directive's words and in any expected text: `{home}` is `ctxlang/`,
   `{repo}` the repository's root, `{exe}` an executable's suffix (`.exe` or nothing). A
   directory case has more (below).
7. **A word** of `args:` is separated by spaces; in double quotes it may hold spaces and the
   escapes of rule 4, and `""` is the empty word.
8. **A platform tag** before a directive's key, `//# [windows] exit: 3`, makes it apply on that
   platform only: `[windows]`, `[linux]`, `[macos]`, `[posix]`.
9. **`NAME.expect`** beside `NAME.ctx` holds the directives instead, and then nothing in
   `NAME.ctx` is read as a directive or a marker: for a program whose bytes matter, as one that
   ends without a line break or in the middle of a comment. Positions are then written in full,
   with `errors:` and `panic:`.

A program that reads no files and starts no programs needs nothing else. One that does is a
directory.

## A case that is a directory

A directory with a file named `CASE` is one case; nothing in it is another. `CASE` holds the
directives, with the same syntax, and plain `//` lines are comments. The runner copies the
directory to `build/suite/work/NAME` and runs the case there, so it may write files.

`CASE` is a list of steps, run in order until one fails. A step starts with one of these, and
the directives after it, up to the next step, are about it:

| Step | Meaning |
|---|---|
| `//# program: FILE...` | Builds the program of those files, runs it and compares it with the interpreter: as a case of one file, with all of that case's directives, and `//~` markers in the files. |
| `//# build NAME: FILE...` | Builds the program, for later commands to run as `{NAME}`. It may state `errors:` (or markers), and `env:`. |
| `//# project` | Builds the directory's `build.ctx` project as `ctxc graph` describes it: each executable it names is built as the harness builds any program, and run as `{NAME}`. It may state `errors:` (ctxc's, of the build program or of an executable's files), `panic:` or `exit:` (the build program's), `stdout:`, `stderr:` and `env:`. |
| `//# $ WORD...` | Runs a command, whose first word is `ctxc` (the ctxc under test, with `CTX_HOME` set), `cc` (the harness's C compiler), `ar`, `suite` (this runner itself, on other cases: [cases/Suite](cases/Suite) checks with it that broken cases fail), `{NAME}` (an executable a step built) or `./PATH` (one a command made, in the case's directory). It states `exit:`, `stdout:`, `stderr:` and `panic:` as a program does, and takes `stdin:`, `env:`, `cwd: DIR`, `stack:` and `timeout:`. |
| `//# write PATH:` + block | Writes a file (`write PATH escaped:` with escapes). |
| `//# remove PATH` | Removes a file, or a directory and all in it. |
| `//# make dir PATH` | Makes a directory. |
| `//# exists PATH`, `//# missing PATH` | Expects a file or a directory to be there, or not. |

After a step that runs something, `//# file PATH:` + block expects a file's text, and
`//# list PATH:` + block the names in a directory, sorted, a line for each (`has`, `lacks`,
`escaped` and wildcards as for `stdout`).

More placeholders: `{dir}` is the directory the case runs in, absolute, with `/`; `{NAME}` an
executable built by `build NAME:` or a project; `{ctxc}` the ctxc under test; `{cc}` the C
compiler's command; `{gen}` where a project's generated files go; and `{work:PATH}` the
directory ctxc builds the program at PATH in (`{work:.}` for `ctxc run .`). As a whole word of a
command, `{std}` is std's files for this platform, as paths from the command's directory,
`{std:abs}` by their absolute paths, and `{std:linux}`, `{std:macos}`, `{std:windows}` and
`{std:interp}` another layer's; `{cflags}` is the flags the harness compiles C with, and
`{stack}` those that reserve its stack.

A command and a project state what they expect as a program does: a `$` step with no `exit:`,
`stdout:`, `stderr:` or `panic:` fails as stating nothing, standard output and standard error
are compared whole unless a `has`, `lacks` or `any` form says otherwise, and the exit code is 0
unless stated.

The directories ctxc builds in for `ctxc run`, `exe`, `test` and `graph` commands
(`build/run/NAME-HASH`) are removed before and after the case, so each run of it builds from
nothing.

```
// `ctxc test` prints a line for each test with -v, then the count.
//# $ ctxc test . -v
//# stdout:
//| ./t.ctx:4: pass: doubles
//| tests: 1 run, 1 passed, 0 failed, 0 skipped, 0 not selected, 2 checks
```

Programs that cases share are in [helpers/](helpers), each with its uses in its header:
`child.ctx` is a child process for the cases that start one, `logcc.ctx` a C compiler that logs
its command lines, `stamp.ctx` says whether a file was written again, and `text.ctx` runs a
command into a file, compares files and counts a pattern. A case builds one with
`//# build child: {home}/tests/helpers/child.ctx`.

## Adding a case

1. Write the program as `cases/GROUP/NAME.ctx`. Put a comment on top that says what it shows.
2. State what it should do: `//# stdout:` and its block after the program, or `//~ error at
   COL: MESSAGE` on the line of each error.
3. Run it: `kotor/tools/ctxc run ctxlang/tools/suite -- GROUP/NAME`. A failure prints the actual
   text in the block's form, to compare with what was meant, never to paste unread.

There is no mode that rewrites expectations: a case says what its author expects.

Files under `cases/` are stored byte for byte (`.gitattributes`: no line-ending conversion),
with LF line ends; a case that needs other bytes (a CR, a NUL, no final line break) is a
`NAME.expect` case or states them `escaped`.
