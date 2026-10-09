# Threads: design draft

Status: draft for review. Nothing here is implemented. When it is accepted, the parts that change the
language move into spec.md, and the rest becomes std and runtime work, on a branch of its own
(kotor/AGENTS.md, rule 1).

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
        stack_size: usize,          // bytes; 0 means the platform's default (1 MiB on Windows)
        name: []u8,                 // shown by debuggers and in panic reports; may be empty
    }

    error out_of_resources          // the operating system refused another thread

    fn default_options {} -> Options

    // Starts a thread that runs `run{ data }` and ends when it returns.
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

**New rule.** `thread::create` passes the run function's capabilities the way a direct call to it
would: the caller must hold each one, or `create` doesn't compile. This is the only part of layer 1
that the compiler has to check. Without it, a thread could do things its creator has no permission
for.

A capability with fields (a library's functions, spec §15, rule 5) is passed the same way: the thread
gets a copy, which can't change (rule 8).

### Atomics

Atomics are builtins, because they must compile to single machine instructions on any integer, `bool`
or pointer type. The memory order is an enum in std:

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
@atomic_add(p, value, order) -> T                          // integers; gives the old value
@atomic_subtract(p, value, order) -> T
@fence(order)
```

Example: a counter that several threads add to.

```
let before = @atomic_add(&shared.count, 1, atomic::Order::relaxed)
```

### Mutexes and conditions

These are std, over the operating system's (Windows' slim reader/writer locks and condition variables,
POSIX's `pthread_mutex_t` and `pthread_cond_t`). They need no capability: they only block, and only
matter once there are threads.

```
namespace mutex {
    struct Mutex { ... }            // the platform's lock; lives in the memory the threads share

    fn make {} -> Mutex
    fn lock { mut mutex: Mutex }
    fn try_lock { mut mutex: Mutex } -> bool
    fn unlock { mut mutex: Mutex }
    fn free { mut mutex: Mutex }    // nothing on Windows; pthread_mutex_destroy elsewhere
}

namespace condition {
    struct Condition { ... }

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
mutex::lock{ &shared.lock }
defer mutex::unlock{ &shared.lock }
while shared.queue_length == 0 {
    condition::wait{ &shared.not_empty, &shared.lock }
}
```

### Thread-local statics

```
capability Counters {
    #thread_local
    static frames: u64
}
```

`#thread_local` on a capability's static (spec §15, rule 13) gives each thread its own copy, starting
at the type's zero value. It is C11's `_Thread_local`.

### Callbacks from other threads

Spec §18, Callbacks, rule 6 says C must call a callback on the thread that called into C. SDL's audio
callback breaks that: SDL calls it from its own thread. The proposal:

```
#c::callback{ any_thread = true }
fn fill_audio { data: *mut Ring, stream: *mut u8, length: i32 } { ... }
```

`any_thread = true` allows any thread to call it. Such a callback may take no capability (the thread it
runs on received none), and it starts with the stack check off, since that thread's limit is unknown.
State reaches it through C's user pointer, as for other callbacks.

### What the runtime and std must change

Even with memory left to the programmer, the runtime's own shared state has to stay correct:

| Shared state today | Change |
|---|---|
| The stack-limit static (`rt::Stack`, `#stack_limit`) | thread-local. The runtime sets it at each thread's start, from the thread's own stack bounds |
| A panic | still ends the whole program. The report names the thread (its `name`, else its id), and only one thread reports, through an atomic flag |
| Standard output's buffer (`io::State`'s `out` static) | thread-local, flushed when its thread ends and at exit; lines from different threads may interleave, but bytes won't tear |
| Memory for function values' records (`rt::pages_set`) | a lock around the runtime's allocator, or a block per thread |
| `mem::pages`, `mem::reserve` | already safe: they call the operating system |
| Arenas, lists, maps | unchanged and not safe to share: one thread at a time, as in C |
| The interpreter (`ctxc interp`, `std/os/interp`) | open question (below) |

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
        mutex::lock{ &m.commands.lock }
        let n = m.commands.count
        slice::copy(Command){ dst = taken[..n], src = m.commands.items[..n] }
        m.commands.count = 0
        mutex::unlock{ &m.commands.lock }
        apply_all{ m, commands = taken[..n] }
        top_up_queue{ &sdl, m }     // mixes what the device lacks
        thread::sleep{ &threads, nanoseconds = 5000000 }
    }
}

// On the main thread: play a sound.
fn play { mut mixer: Mixer, sound: u32, x: f32, y: f32, z: f32 } -> u32 {
    let handle = @atomic_add(&mixer.next_handle, 1, atomic::Order::relaxed)
    mutex::lock{ &mixer.commands.lock }
    defer mutex::unlock{ &mixer.commands.lock }
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

## Open questions

1. **The interpreter.** `ctxc interp` runs programs over `std/os/interp`. Either it runs threads one
   at a time, switching at each `mutex`, `condition`, `channel` or `sleep` call (deterministic, good
   for tests), or it refuses programs that take `Threads`.
2. **Bound functions for `create`.** Allowing `thread::create{ ..., run = mix_loop{ &mixer, _ } }`, with
   the record kept until the thread ends, reads better than a data pointer, but changes spec §6,
   rule 3. Worth it later?
3. **Joining before the frame ends.** Should the compiler warn when `data` points into the creating
   function's own locals and the thread isn't joined before it returns? The escape check could see
   the simple cases.
4. **Sleeping without the capability.** Should `sleep` and `yield_now` need `Threads`? As drafted they
   do, so a run function that sleeps takes `Threads` (the mixer above does). Sleeping has no effect
   outside the program, so they could be free of it instead.
5. **Thread names on the platform.** Windows wants UTF-16 (`SetThreadDescription`), POSIX caps names
   at 16 bytes. Truncate silently?
