# Threads: design

Status: **layer 1 is implemented**, all of it (below, "Layer 1: what was built"): the language's part
is in spec.md (§13 Atomics, §15 rules 13 and 14 and Entry point rule 8, §17, §18 Attributes and
Callbacks), std's in std/thread.ctx and the platform layers, the runtime's in ctxc/rt. Layers 2 and 3
are future work. The game doesn't use threads yet.

## Why

A ctxlang program runs on one thread. Two needs in the KOTOR port have no good answer without more:

- **Sound.** The game mixes sound on its main thread and queues it to SDL about 60 ms ahead. Any frame
  slower than that (a model loading, a shader compiling, an area changing) empties the queue and the
  sound drops out. A mixer on a thread of its own keeps playing whatever the main loop does.
- **Loading.** Models, textures and areas load on the main thread, so the game freezes while they do.
  A loader thread could decode them while the game runs.

## Shape: three layers

1. **Threads** (the language and the runtime): real operating-system threads, atomics, mutexes,
   conditions and thread-local statics. Nothing stops two threads from sharing memory: managing it is
   the programmer's job, as in C. This layer gives power, not safety.
2. **Channels** (std, written in ctxlang over layer 1): typed queues between threads, with an optional
   check that what is sent holds no pointer.
3. **Task pools** (std, over layers 1 and 2): a fixed set of worker threads that run queued jobs. This
   is the useful part of Go's goroutines for a game. Lightweight threads that switch stacks (Go's
   scheduler) are out of scope.

Each layer uses only the one below it, so a program that wants the raw layer never pays for the others.

**Scope now: layer 1 only.** Layers 2 and 3 are future work, sketched below so layer 1 leaves room for
them. The first use is the game's sound mixer (Examples), which needs only this slice of layer 1:

1. `Threads`, `thread::create`, `join`, `sleep`, and the compiler rule for a run function's
   capabilities;
2. `mutex::make`, `lock`, `unlock`, `free`, and `@atomic_load`, `@atomic_store`, `@atomic_add`;
3. the runtime's part: a stack limit per thread, a panic on any thread reported once, a lock on the
   memory for function values' records.

`#thread_local`, conditions and `#c::callback{ any_thread = true }` follow when something needs them.

## Layer 1: threads

The API as built. Where it differs from the first draft, "Decisions" (below) says why.

### Permission

```
// Permission to start threads.
capability Threads
```

`main` receives it like `Io`, `Fs` or `Mem`, and passes it down to code that may start threads. A
function without it can't start one.

### Creating and joining

```
namespace thread {
    // A running thread, as the operating system knows it.
    struct Thread { handle: u64 }

    struct Options {
        stack_size: usize,          // bytes the thread may use; 0 means DEFAULT_STACK, 8 MiB
        name: []u8,                 // for debuggers and panic reports, cut to 63 bytes; may be empty
    }

    error out_of_resources          // the operating system refused another thread

    const DEFAULT_STACK: usize = 8388608

    fn default_options {} -> Options

    // Starts a thread that runs `run{ data }` and ends when it returns.
    #spawn
    fn create(T) { mut threads: Threads, run: fn{ data: *mut T }, data: *mut T, options: Options } -> !Thread

    // Waits for the thread to end. Each thread is joined or detached exactly once.
    fn join { mut threads: Threads, thread: Thread }

    // Lets the thread end on its own; its handle is no longer valid.
    fn detach { mut threads: Threads, thread: Thread }

    // The calling thread waits at least this long.
    fn sleep { mut threads: Threads, nanoseconds: u64 }

    // Gives the rest of the calling thread's time slice to another thread.
    fn yield_now { mut threads: Threads }

    // A number unique to the calling thread while it runs.
    fn current_id {} -> u64
}
```

`create` is generic over `T`, as `pthread_create` takes a `void *`, but typed. It doesn't copy `*data`
and doesn't keep it alive: the memory behind `data` must outlive the thread. That's the caller's
responsibility, and nothing checks it.

Why a plain `fn` and a pointer, and not a bound function (`&fn`): a bound function's capture record
lives only until the function that made it returns (spec §6, rule 3), and a thread usually outlives
that.

### Capabilities on a new thread

The run function may take capabilities besides `data`:

```
fn mix_loop { mut io: Io, data: *mut Mixer } { ... }

let t = try thread::create{ &threads, run = mix_loop, data = &mixer, options = thread::default_options{} }
```

**New rule** (spec §15, rule 14). `thread::create` passes the run function's capabilities the way a
direct call to it would: the caller must hold each one, or `create` doesn't compile. Without it, a
thread could do things its creator has no permission for.

How it is built: `#spawn`, an attribute the compiler declares, marks a fn whose read-only field `run`
has a `fn` type; std's `thread::create` has it. At a call to such a fn, the argument for `run` may be
a function whose context has capabilities beyond `run`'s type. The checker supplies each as `..`
would to a direct call (spec §3, rule 7): the caller's local or context field of the same name, a
mutable place for a `mut` one, converting to an included capability as any argument does. A missing
one is an error at the call: "`mix_loop` takes capability `sdl`, which a thread receives from its
creator: no local or context field named `sdl` holds one here". Lowering then makes the argument a
`fn` of `run`'s type: a thunk that calls the run function with the capabilities (lower.ctx,
`carried`). One without fields comes from nothing, as `main`'s do, so a named run function that
takes only those needs no record at all. One with fields (a library's functions, spec §15, rule 5)
is copied at the call into a record that lives as long as the program (ctx_alloc), since the
thread may outlive its creator; a copy can't change (rule 8). Such a record is the only memory a
thread start keeps for good, a few words for each `create` whose run function takes a capability
with fields.

The attribute, rather than knowledge of `thread::create` by name, leaves the rule to any fn that
runs a function elsewhere: layer 3's `task::run` is the next.

### Atomics

Atomics are builtins, because they must compile to single machine instructions on any integer, `bool`,
enum or pointer type (a `?*T` too). The memory order is an enum in std, and must be a constant, so
that it is C's at compile time: a load can't release and a store can't acquire (spec §13, Atomics).
They lower to GCC's `__atomic` builtins, which gcc, Apple clang and zig cc all have; the interpreter
does each as the plain access, since it runs one thread at a time.

```
namespace atomic {
    enum Order: u8 { relaxed, acquire, release, acquire_release, sequentially_consistent }
}

@atomic_load(p, order) -> T                                // p: *T
@atomic_store(p, value, order)                             // p: *mut T
@atomic_exchange(p, value, order) -> T                     // stores value, gives the old one
@atomic_compare_exchange(p, expected, desired, order) -> ?T
                                                           // stores desired if *p == expected;
                                                           // null on success, else the value found
@atomic_add(p, value, order) -> T                          // integers, wrapping; gives the old value
@atomic_subtract(p, value, order) -> T
@fence(order)
```

Example: a counter that several threads add to.

```
let before = @atomic_add(&shared.count, 1, atomic::Order::relaxed)
```

A result must be used, as a call's: `_ = @atomic_add(...)` discards it. What a store puts through the
pointer can't hold a local's address (spec §14), as for a store through any pointer.

### Mutexes and conditions

These are std, over the operating system's (Windows' slim reader/writer locks and condition variables,
POSIX's `pthread_mutex_t` and `pthread_cond_t`). They need no capability: they only block, and only
matter once there are threads.

```
namespace mutex {
    type Mutex = os::Mutex          // the platform's lock; lives in the memory the threads share

    fn make {} -> Mutex
    fn lock { mut mutex: Mutex }
    fn try_lock { mut mutex: Mutex } -> bool
    fn unlock { mut mutex: Mutex }
    fn free { mut mutex: Mutex }    // nothing on Windows; pthread_mutex_destroy elsewhere
}

namespace condition {
    type Condition = os::Condition

    fn make {} -> Condition
    // Unlocks `mutex`, waits for a signal, locks it again. May wake without one: check again.
    fn wait { mut condition: Condition, mut mutex: mutex::Mutex }
    // As `wait`, giving up after `nanoseconds`; false when it gave up.
    fn wait_for { mut condition: Condition, mut mutex: mutex::Mutex, nanoseconds: u64 } -> bool
    fn signal { mut condition: Condition }          // wakes one waiting thread
    fn broadcast { mut condition: Condition }       // wakes them all
    fn free { mut condition: Condition }
}
```

The usual pattern, with `defer`:

```
mutex::lock{ mutex = &shared.lock }
defer mutex::unlock{ mutex = &shared.lock }
while shared.queue_length == 0 {
    condition::wait{ condition = &shared.not_empty, mutex = &shared.lock }
}
```

A `Mutex` is a slim reader/writer lock on Windows and a `pthread_mutex_t` elsewhere, made from its
static initializer (zeros, or macOS's signature word), so `make` needs no call into C. A Windows
`Condition` is a condition variable, and `wait_for` rounds its time up to milliseconds; POSIX's waits
until a time of the realtime clock.

### Thread-local statics

```
capability Counters {
    #thread_local
    static frames: u64
}
```

`#thread_local` on a capability's static (spec §15, rule 13) gives each thread its own copy, starting
at the type's zero value. It is C11's `_Thread_local`, in a threaded program only (below): in any
other the one thread has the one static, as without it. std's io `out`, standard output's 64 KiB
buffer, is one.

### Callbacks from other threads

Spec §18, Callbacks, rule 6 says C must call a callback on the thread that called into C. SDL's audio
callback breaks that: SDL calls it from its own thread. The proposal:

```
#c::callback{ any_thread = true }
fn fill_audio { data: *mut Ring, stream: *mut u8, length: i32 } { ... }
```

`any_thread = true` allows any thread to call it. Such a callback may take no capability (the thread it
runs on received none), and it starts with the stack check off, since that thread's limit is unknown.
State reaches it through C's user pointer, as for other callbacks. Built as drafted (spec §18,
Callbacks, rule 6). An attribute may now leave out a field of a number or `bool` type, which is then
0 or false (spec §18, Attributes, rule 2), so every `#c::callback` without braces stays as it was.

Every callback's C function, in a threaded program, gives a thread that has no runtime state (one the
program didn't start) state on its own frame until it returns: its stack limit is 0, so the check is
off, and its records of function values are its own. std's own thread entry is such a callback
(`os::thread_entry`): the OS calls it on the new thread, and it calls `thread::begin`.

### What the runtime and std changed

Even with memory left to the programmer, the runtime's own shared state has to stay correct. Every
static of std's and every global of the runtime's, and what became of it:

| Shared state | What it is now |
|---|---|
| The stack limit (`rt::Stack`'s `#stack_limit` static) | per thread. Its storage is the runtime's (`ctx_thread.stack_limit`, CTX_STACK_LIMIT in C). std's start sets the main thread's as before; `thread::begin` sets a new thread's to its frame less the stack it may use (`ctx_thread_begin`), and its stack is reserved larger than that, by a quarter or at least 1 MiB, so a frame that crosses the limit reaches the check and the panic is reported. A thread the program didn't start has 0: no check |
| A panic (ctxrt.c, `report`) | still ends the whole program. Only one thread reports, through an atomic flag; a panic on another thread meanwhile spins until the program ends, and one on the reporting thread traps. std's report says `panic in thread NAME:`, NAME being the thread's name, else its OS id |
| Standard output's buffer (`io::State`'s `out` static) | `#thread_local`, written out when its thread ends (`rt::thread_ends`, which std's start gives the runtime: `ctx_ends_set`) and by the main thread at exit and on a panic; lines from different threads may interleave, but bytes won't tear. A detached thread still running at exit loses what it hasn't written out |
| Function values' records (ctxrt.c) | borrowed records: a stack of segments per thread; an ending thread's segments go to a pool the next thread takes them from. Pages for them, permanent records (`ctx_alloc`) and the table of adapters (`ctx_adapt`): behind a spin lock, on only in a threaded program |
| `proc::State`'s `exe_path` (the executable's path, once asked for) | `#thread_local`: each thread asks once, rather than two threads writing one slice |
| `build::State`'s `graph` | unchanged: a build program has one thread |
| ctxrt.c's file table, program name, panic fn and pages fn | set once by C's main and std's start, before any thread starts: read only after |
| `mem::pages`, `mem::reserve` | already safe: they call the operating system |
| Arenas, lists, maps | unchanged and not safe to share: one thread at a time, as in C |
| The interpreter (`ctxc interp`, `std/os/interp`) | runs one thread at a time (Decisions, 1) |

### Threaded programs: what a program without threads pays

Nothing (spec §15, Entry point, rule 8). A program is **threaded** if `main` or its start fn takes
`Threads`, or it has a `#c::callback{ any_thread = true }`; which it is depends on the source alone,
with no switch in the build program. Only a threaded program's C defines `CTX_THREADS`, before it
includes ctxrt.h, and only it is linked with ctxc/rt/ctxthread.c (and `-lpthread` on Linux, for glibc
before 2.34). Then:

- `CTX_HERE`, the calling thread's runtime state, is a thread-local pointer: on Windows x64 a TLS slot
  read straight from the TEB (`gs:[0x1480 + 8 * slot]`), since MinGW's `_Thread_local` is a call to
  `__emutls_get_address` (fib(35) took 296 ms with it against 37 ms with a global; 38 ms with the
  slot); elsewhere a `_Thread_local`.
- The stack limit is thread-local on its own, to keep the check short: a second TEB slot on Windows,
  whose number the check reads from its symbol, and a `_Thread_local` elsewhere. A `#thread_local`
  static is `_Thread_local`.
- ctxrt.c's lock is on, and every callback's C function gives a thread without state its own.

In any other program `CTX_HERE` is the address of the main thread's state, a plain global: the stack
check and the records are what they were, nothing locks, and no thread library is linked.

Measured on Windows (gcc 15, `ctxc exe`, -O1), each program built as it is and as a copy whose `main`
also takes `Threads` without starting a thread:

| Program | Not threaded | Threaded |
|---|---|---|
| hello world: executable | 140,585 bytes | 146,237 bytes |
| examples/wordcount.ctx: executable | 159,885 bytes | 165,892 bytes |
| fib(38), about 126 million calls and nothing else | 0.163 s | 0.19–0.20 s |
| wordcount of spec.md | 9–12 ms | 9–13 ms (noise) |

The threaded check is two loads, the slot's number and the TEB's slot, where the plain one is one; on
a program that does nothing but call, that is a fifth more time, and on a real one it doesn't show.
In C alone, fib(36) took 59 ms with a global limit and 62–64 ms with the TEB slot; MinGW's
`_Thread_local` would have been eight times slower.

ctxc already leaves unused functions out: lowering starts from `main`, the start fn and the panic fn
and lowers only the instances they reach, so nothing unreachable gets to C. The runtime's objects are
linked whole, but ctxfloat.c only when floats are written or read and ctxthread.c only in a threaded
program. `-ffunction-sections -fdata-sections -Wl,--gc-sections` is no win with MinGW: hello world's
unstripped executable grew from 363 KB to 514 KB with them.

## Layer 2: channels (future)

A channel is a queue of `T` with a fixed capacity, written in ctxlang over a mutex and two conditions.
It lives in memory both threads can reach.

```
namespace channel {
    struct Channel(T, S) { ... }    // a ring of `capacity` values, a mutex, "not empty", "not full"

    error closed                    // sending to a closed channel

    // A channel of up to `capacity` values, its ring from `realloc`. T must hold no pointer
    // (below); `make_unchecked` skips that check.
    fn make(T, S) { realloc: alloc::Fn(S), heap: *mut S, capacity: usize } -> !Channel(T, S)
    fn make_unchecked(T, S) { realloc: alloc::Fn(S), heap: *mut S, capacity: usize } -> !Channel(T, S)

    // Waits while the channel is full.
    fn send(T, S) { mut channel: Channel(T, S), value: T } -> !
    // Waits while it is empty. Null once it is closed and empty.
    fn receive(T, S) { mut channel: Channel(T, S) } -> ?T

    // Without waiting: false (or null) when it would have to wait.
    fn try_send(T, S) { mut channel: Channel(T, S), value: T } -> !bool
    fn try_receive(T, S) { mut channel: Channel(T, S) } -> ?T

    // No more sends; receivers drain what is left, then get null.
    fn close(T, S) { mut channel: Channel(T, S) }
    fn free(T, S) { mut channel: Channel(T, S) }
}
```

**The pointer check.** `make` refuses, at compile time, a `T` that holds a pointer or a slice. A value
without one can't share memory, so a channel of such values can't race. The compiler already knows
which types hold a pointer (its escape check, spec §14); the proposal exposes that as a builtin,
`@holds_pointer(T)`, which `make` checks in a constant. Sending pointers is still possible, with
`make_unchecked`, when the program has its own reason to know the memory is safe, for example sound
samples loaded once and never freed.

**Waiting on several channels** (Go's `select`) needs either a builtin or a generic that ctxlang
generics can't express yet. It's left out of the first version; one thread per input works meanwhile.

## Layer 3: task pools (future)

Go's goroutines are cheap because Go switches stacks in user space and grows them as needed. ctxlang's
fixed stacks and per-function stack check make that a large runtime project, and a game doesn't need
thousands of tasks. What it needs is "run this job on some other thread", and that is a pool:

```
namespace task {
    struct Pool(S) { ... }          // workers, a channel of jobs, a count of unfinished jobs

    // Starts `workers` threads that wait for jobs.
    fn make_pool(S) { mut threads: Threads, realloc: alloc::Fn(S), heap: *mut S, workers: u32 } -> !Pool(S)

    // Queues `run{ data }` for the next free worker.
    fn run(T, S) { mut pool: Pool(S), run: fn{ data: *mut T }, data: *mut T } -> !

    // Waits until every queued job has finished.
    fn wait_all(S) { mut pool: Pool(S) }

    // Finishes the queued jobs, ends the workers, frees the pool.
    fn free(S) { mut threads: Threads, mut pool: Pool(S) }
}
```

Jobs follow the same rules as `thread::create`: the data must outlive the job.

## Examples

### A sound mixer thread with layer 1 only

The mixer thread owns every voice, mixes, and calls `SDL_QueueAudio` itself (SDL allows that from any
thread), so a stalled main thread no longer empties the queue. The game hands it commands through a
small queue guarded by a mutex; handles come from an atomic counter, so playing a sound never waits on
the mixer.

```
struct Commands {
    lock: mutex::Mutex,
    items: [256]Command,
    count: u32,
}

struct Mixer {
    commands: Commands,             // the only part both threads touch, under its lock
    next_handle: u32,               // atomic
    running: u32,                   // atomic: 0 asks the mixer thread to end
    // voices, the device, the listener: the mixer thread's alone
}

fn mix_loop { mut sdl: sdl::Sdl, mut threads: Threads, data: *mut Mixer } {
    let m = data
    let mut taken: [256]Command
    while @atomic_load(&m.running, atomic::Order::acquire) == 1 {
        mutex::lock{ mutex = &m.commands.lock }
        let n = m.commands.count
        slice::copy(Command){ dst = taken[..n], src = m.commands.items[..n] }
        m.commands.count = 0
        mutex::unlock{ mutex = &m.commands.lock }
        apply_all{ m, commands = taken[..n] }
        top_up_queue{ &sdl, m }     // mixes what the device lacks
        thread::sleep{ &threads, nanoseconds = 5000000 }
    }
}

// On the main thread: play a sound.
fn play { mut mixer: Mixer, sound: u32, x: f32, y: f32, z: f32 } -> u32 {
    let handle = @atomic_add(&mixer.next_handle, 1, atomic::Order::relaxed)
    mutex::lock{ mutex = &mixer.commands.lock }
    defer mutex::unlock{ mutex = &mixer.commands.lock }
    if mixer.commands.count < 256 {
        mixer.commands.items[mixer.commands.count] = Command::play{ handle, sound, x, y, z, volume = 1.0 }
        mixer.commands.count = mixer.commands.count + 1
    }
    return handle
}
```

The memory both threads read is the game's to manage. Sound samples are decoded into the module's
memory, which is reset on an area change: before the reset, the game sends "drop every voice" and waits
until the mixer says it has, or the mixer would read freed memory. And until standard output's buffer is
thread-local, the mixer thread doesn't print: it counts what it would report (underruns, stolen voices)
in atomics that the main thread prints.

### The same mixer with a channel (layer 2, future)

With layer 2 the command queue becomes a channel, and the code above shrinks to sends and receives.

```
// Pointer-free, so it passes the channel check.
union Command {
    play{ handle: u32, sound: u32, x: f32, y: f32, z: f32, volume: f32 },
    stop{ handle: u32 },
    listener{ x: f32, y: f32, z: f32, facing: f32 },
    quit{},
}

struct Mixer {
    commands: channel::Channel(Command, heap::Heap),
    // voices, sounds and the device, touched by the mixer thread only
}

fn mix_loop { mut sdl: sdl::Sdl, mut threads: Threads, data: *mut Mixer } {
    let m = data
    while true {
        while channel::try_receive{ channel = &m.commands } is some{ value = c } {
            match c {
                quit{} => { return }
                else => { apply{ m, c } }
            }
        }
        top_up_queue{ &sdl, m }         // mixes what the device lacks
        thread::sleep{ &threads, nanoseconds = 5000000 }
    }
}

// On the main thread:
let mut mixer = try make_mixer{ ... }
let worker = try thread::create{ &threads, run = mix_loop, data = &mixer, options = thread::default_options{} }
...
try channel::send{ channel = &mixer.commands, value = Command::play{ sound = blaster, x, y, z, volume = 1.0 } }
...
try channel::send{ channel = &mixer.commands, value = Command::quit{} }
thread::join{ &threads, thread = worker }
```

### Background loading (layer 3, future)

```
struct TextureJob { name: [32]u8, pixels: []mut u8, done: u32 }   // `done` is set atomically

fn decode_texture { mut fs: Fs, data: *mut TextureJob } {
    // reads and decodes into data.pixels, which the main thread gave it
    @atomic_store(&data.done, 1, atomic::Order::release)
}

let mut pool = try task::make_pool{ &threads, realloc = heap::alloc, heap = &heap, workers = 3 }
try task::run{ &pool, run = decode_texture, data = &job }
...
if @atomic_load(&job.done, atomic::Order::acquire) == 1 { upload{ &dev, job } }
```

## Layer 1: what was built

| Piece | Where | Tests (tests/test_ctxlang.py, class Threads) |
|---|---|---|
| `Threads`, `thread::create`, `join`, `detach`, `sleep`, `yield_now`, `current_id`, `out_of_resources` | std/thread.ctx; std/os/windows (CreateThread, WaitForSingleObject, SetThreadDescription), std/os/posix (pthread_create, pthread_join, nanosleep, pthread_setname_np), std/os/interp | create, join and data; a `fn` value as run function |
| A run function's capabilities, `#spawn` | check.ctx (`carry`), lower.ctx (`carried`), emit_c.ctx (a `fn` bind's record for good) | capabilities on a thread; the caller lacking one; a read-only one where `mut` is needed; a bound function refused; a capability with fields |
| Atomics, `atomic::Order` | parser, check.ctx (`atomic_builtin`), lower.ctx, IR `atomic`, emit_c.ctx (`__atomic_*`), eval.ctx | every atomic on integers, `bool`, an enum and pointers; the errors |
| `mutex` | std/thread.ctx; SRWLOCK, `pthread_mutex_t` | try_lock, lock, unlock; the stress test |
| `condition` | std/thread.ctx; CONDITION_VARIABLE, `pthread_cond_t` | a producer and a consumer, and `wait_for` giving up |
| `#thread_local` | check.ctx, IR `Static.local`, emit_c.ctx | a static of each thread's; the same program not threaded |
| Threaded programs | lower.ctx (`threaded_program`), emit_c.ctx, ctxrt.h, ctxthread.c, drive.ctx | the C of a program with and without `Threads` |
| Runtime: stack limit per thread, panics, records | ctxrt.c, ctxthread.c | a panic on a thread (its name in the report); a stack overflow on a thread caught by its own limit |
| `#c::callback{ any_thread = true }` | check.ctx, std/c.ctx; every callback's C function in a threaded program | std's thread entry on every platform is one |
| Stress | | 8 threads × 1,000,000 increments of one atomic counter and of one counter under a mutex: 8,000,000 each, every run |

The POSIX layer is written and compiled, not run: this machine runs Windows. ctxc builds a threads
program's C for Linux and for macOS (`ctxc build` with their platform layers), and that C compiles;
linking and running it is left for a machine that can.

## Order of work

1. Runtime: threads on Windows and POSIX, a stack limit per thread, panics from any thread, a locked
   record allocator. (Thread-local standard output comes with `#thread_local`, later.)
2. Compiler: the `Threads` capability, the capability rule for `thread::create`, the atomic builtins.
3. std: `thread`, `mutex`, `atomic`.
   - Later in layer 1, when something needs them: `condition`, `#thread_local`,
     `#c::callback{ any_thread = true }`.
4. Tests: corpus programs for each piece, including a stress test (several threads adding to one
   atomic counter and to one mutex-guarded counter, checked against the expected total), then the
   bootstrap refresh (ctxlang/PLAN.md, "Changing the language").
5. The game: the mixer thread (Examples).
6. Future: layer 2 (`channel`, `@holds_pointer`), then layer 3 (`task`) and the loader pool.

## Decisions

1. **The interpreter** (was open question 1): it runs a thread to its end inside `thread::create`,
   before the creator goes on, with its own `#thread_local` statics, and `join` returns at once. That
   is one schedule the program's threads may really have, and the same on every run, so the suite's
   threads programs whose threads don't wait on each other run both ways and must match: create and
   join, capabilities on a thread, a panic on a thread, thread-local statics, the atomics, a mutex. A
   thread that would wait for another (a mutex another holds, a condition's `wait`) stops the run as
   not supported by interp, as files do; `wait_for` gives up at once, and `sleep` and `yield_now` do
   nothing. Switching between threads at blocking calls would need the evaluator to keep several
   stacks, since it is recursive; refusing programs that take `Threads` would have tested none of it.
   Programs that need real concurrency (the condition test, the stress test) run compiled only.
2. **How `create` knows the run function's capabilities**: an attribute, `#spawn`, that the compiler
   declares and std's `create` has, rather than a builtin `create` wraps (a builtin inside `create`
   would hold only `create`'s own capabilities, not its caller's) or `thread::create` by name. The
   caller holds them by name, as `..` finds them.
3. **Sleeping takes `Threads`** (was open question 4): kept as drafted. A function that sleeps says
   so, which the mixer's loop does anyway.
4. **Thread names** (was open question 5): cut silently, to 63 bytes for the panic report and
   Windows (`SetThreadDescription`, after UTF-16), to 15 on Linux and 63 on macOS
   (`pthread_setname_np`, which macOS applies only to the calling thread: `begin` sets it there). A
   thread without a name is named by its id in a panic's report, not for debuggers.
5. **The default stack**: 8 MiB everywhere (`thread::DEFAULT_STACK`), not each platform's own
   (Windows' would be the executable's 256 MiB, macOS's 512 KiB), so the stack limit is known. The
   stack is reserved a quarter larger, at least 1 MiB more, for the check to land in.
6. **Threaded programs** (added after the draft): the threaded runtime only where the source asks
   for it (above), so a program without threads pays nothing.
7. **A thread's end** writes out its standard output through a fn std's start gives the runtime
   (`ctx_ends_set`, as `pages_set` gives memory for records): `thread::begin` holds no `Io`, and a
   callback that any thread may call holds no capability.

## Open questions

1. **Bound functions for `create`.** Allowing `thread::create{ ..., run = mix_loop{ &mixer, _ } }`, with
   the record kept until the thread ends, reads better than a data pointer, but changes spec §6,
   rule 3. Worth it later?
2. **Joining before the frame ends.** Should the compiler warn when `data` points into the creating
   function's own locals and the thread isn't joined before it returns? The escape check could see
   the simple cases.
3. **A thread's records with fields.** A run function that takes a capability with fields keeps a
   copy for good, a few words for each `create`. A pool of threads that starts many could free it
   when the thread ends instead.
