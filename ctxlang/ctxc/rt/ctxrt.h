// ctxrt: the runtime for C that ctxc emits. Needs GNU C (statement expressions, __typeof__,
// overflow builtins, empty structs) on a 64-bit little-endian target.
//
// It is what the C needs that ctxlang can't say itself: the checks the C calls, panics, and
// function values' records. It keeps no state of std's: that is std's statics (spec §15, rule
// 13), but for the stack check's limit, whose storage is a thread's (below). The rest is std's,
// in ctxlang: starting the program (a `#start` fn, std/rt.ctx), reporting a panic (a `#panic`
// fn), and the platform's layer (std/os), which the natives of std are over.
// ctxrt.c calls no C library function. Floats as text and back, which std's
// ascii declares, are ctxfloat.c's, which a program links only if it uses them (ctxc/drive.ctx),
// and the state of each thread of a threaded program is ctxthread.c's, which it links only then.
//
// A program that may run on several threads (spec §15, Entry point, rule 8) is compiled with
// CTX_THREADS, which ctxc defines at the top of its C: then the runtime's state is per thread,
// found through a thread-local pointer. Any other has one thread, whose state is a plain global,
// so it pays nothing for threads.

#ifndef CTXRT_H
#define CTXRT_H

#include <math.h>               // fmod, for `%` on floats
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

_Static_assert(sizeof(void *) == 8, "ctxrt needs 64-bit pointers");

typedef struct { void *ptr; uint64_t len; } ctx_slice;   // []T

// ---- startup
//
// C's main, which ctxc writes (emit_c.ctx, `entry`), gives the runtime the program's file table
// and its `#panic` fn, then calls its `#start` fn.

// A `#panic` fn, as C's main passes it: the message, and the panic's file, line and column,
// with line 0 for a panic without a position. It shouldn't return.
typedef void (*ctx_panic_fn)(ctx_slice msg, ctx_slice file, uint32_t line, uint32_t col);

// `files` names the files positions are in (FNV-1a of each, ctx_panic), and `program` the
// program's path, for panics in files named "" and those without a position: CTX_PROGRAM_NAME,
// which the generated code's includer can define. Without a panic fn, a panic traps.
void ctx_start(const char *const *files, uint32_t nfiles, const char *program, ctx_panic_fn on_panic);
#ifndef CTX_PROGRAM_NAME
#define CTX_PROGRAM_NAME "program"
#endif

// The assembler name of C symbol `name`, a string literal, for an extern fn's prototype.
#define CTX_STR_(x) #x
#define CTX_STR(x) CTX_STR_(x)
#define CTX_SYMBOL(name) CTX_STR(__USER_LABEL_PREFIX__) name

#define CTX_BITCAST(T, x) ({ __typeof__(x) _bc_v = (x); T _bc_r; \
    _Static_assert(sizeof(_bc_r) == sizeof(_bc_v), "bitcast size"); memcpy(&_bc_r, &_bc_v, sizeof _bc_r); _bc_r; })

// ---- panics
//
// Each calls the `#panic` fn once, which C's main gives (ctx_on_panic: it turns the stack check
// off first, so that a stack overflow can be reported); a panic while one is reported, or a panic fn that returns, traps.
// A position is a line, a column, the function it is in and the frame of that function's
// caller (call paths, below). The function is its ctx_where, which ctxc writes before each
// function (emit_c.ctx): its name, its file, and how a call path shows it. `file` is FNV-1a of
// the file's name with the top bit set, which names it in the program's file table, or 0 for
// none; an empty name stands for the program's path.

typedef struct ctx_where { const char *name; uint32_t file; uint32_t kind; } ctx_where;
// kind: a function of the program's; one the compiler wrote, which a path leaves out; where a
// path ends (what calls main, a test or a task); and C code that called a callback.
enum { CTX_SHOWN = 0, CTX_HIDDEN = 1, CTX_ENDS = 2, CTX_C_CODE = 3 };

// A function's frame of the call path: its caller's, itself, and where its last call is, the
// line in the low 20 bits and the column above them (CTX_AT), 0 if it isn't known.
typedef struct ctx_frame { struct ctx_frame *up; const ctx_where *in; uint32_t at; } ctx_frame;

_Noreturn void ctx_panic(uint32_t line, uint32_t col, const ctx_where *in, ctx_frame *up, const char *msg);
// A panic without a position, of a native that a function of the program called, or of the
// runtime's own, which has no call path.
_Noreturn void ctx_panic_nopos(const char *msg);
// std's rt::fail: a panic without a position, whose message isn't a C string.
_Noreturn void ctx_panic_msg(ctx_slice msg);
// The stack check's: in a function whose caller's frame is up.
_Noreturn void ctx_stack_overflow(ctx_frame *up);

#define CTX_POS uint32_t line, uint32_t col, const ctx_where *in, ctx_frame *up

// The checks' messages, with their numbers: "index I out of bounds for length N" and the rest.
_Noreturn void ctx_panic_index(uint64_t i, uint64_t n, CTX_POS);
_Noreturn void ctx_panic_range(uint64_t lo, uint64_t hi, uint64_t n, CTX_POS);
_Noreturn void ctx_panic_index_s(int64_t i, uint64_t n, CTX_POS);
_Noreturn void ctx_panic_range_s(uint64_t lo, uint64_t hi, uint64_t n, int sg, CTX_POS);
_Noreturn void ctx_panic_shift_s(int64_t n, int bits, CTX_POS);
_Noreturn void ctx_panic_shift_u(uint64_t n, int bits, CTX_POS);
_Noreturn void ctx_panic_as_s(int64_t v, const char *dst, CTX_POS);
_Noreturn void ctx_panic_as_u(uint64_t v, const char *dst, CTX_POS);
// A float that isn't representable, in Python's repr: ctxfloat.c's, which writes floats.
_Noreturn void ctx_f2i_fail(double v, const char *dst, CTX_POS);

// ---- threads
//
// The runtime's state for a thread: its stack limit, the storage of the program's `#stack_limit`
// static (spec §15, rule 13); its borrowed records (function values, below); and what a panic on
// it needs. ctx_main_thread is the main thread's. In a threaded program CTX_HERE finds the
// calling thread's through a thread-local pointer, which ctxthread.c keeps: on Windows x64 a
// slot of the thread's TEB, read with one instruction, since MinGW's _Thread_local is a call;
// elsewhere a _Thread_local. A callback that C calls on a thread without one gives it one on its
// frame until it returns (ctx_thread_enter), with the stack check off: such a thread's stack is
// unknown.

typedef struct ctx_rec_seg { struct ctx_rec_seg *next; char *data; char *end; struct ctx_rec_seg *pool; } ctx_rec_seg;
typedef struct { ctx_rec_seg *seg; char *top; char *end; } ctx_rec_mark;

typedef struct ctx_thread {
    uint64_t stack_limit;                  // 0 checks nothing; a threaded program's is CTX_STACK_LIMIT
    ctx_rec_mark recs;                     // the top of its borrowed records
    ctx_rec_seg *head;                     // its first segment of them
    uint32_t growing;                      // taking pages for records
    uint32_t reporting;                    // reporting a panic
    uint64_t name_len;
    char name[64];                         // for a panic's report; empty for the main thread
    ctx_frame *frames;                     // the frame that last called C; a threaded program's is CTX_FRAMES_GET's
    // The panic it reports: the frame of the caller of the function it is in, and its position
    // if it has one.
    ctx_frame *panic_frames;
    const ctx_where *panic_in;
    uint32_t panic_line, panic_col;
    void *task;                            // the record of the task it runs, or null (ctx_thread_task)
} ctx_thread;

extern ctx_thread ctx_main_thread;

#ifdef CTX_THREADS
#if defined(_WIN64) && defined(__x86_64__)
extern uint32_t ctx_thread_slot;            // a TLS slot below 64, whose TEB entry is at gs:0x1480
static inline ctx_thread *ctx_thread_here(void) {
    ctx_thread *t;
    __asm__("movq %%gs:0x1480(,%1,8), %0" : "=r"(t) : "r"((uint64_t)ctx_thread_slot));
    return t;
}
#define CTX_HERE (ctx_thread_here())
// The stack limit has a slot of its own, which the check reads with one instruction.
extern uint32_t ctx_thread_limit_slot;
static inline uint64_t *ctx_thread_limit_at(void) {
    char *teb;
    __asm__("movq %%gs:0x30, %0" : "=r"(teb));
    return (uint64_t *)(teb + 0x1480) + ctx_thread_limit_slot;
}
// The slot's number is read straight from its symbol, which the program links in: GCC would read
// a .refptr first, as for any extern variable on Windows.
static inline uint64_t ctx_thread_limit_now(void) {
    uint64_t v;
    __asm__("movl ctx_thread_limit_slot(%%rip), %k0; movq %%gs:0x1480(,%0,8), %0" : "=r"(v));
    return v;
}
#define CTX_STACK_LIMIT (*ctx_thread_limit_at())
#define CTX_STACK_LIMIT_NOW() ctx_thread_limit_now()
// So has the frame that last called C (call paths, below), which every call of C writes.
extern uint32_t ctx_thread_frames_slot;
static inline ctx_frame *ctx_thread_frames_get(void) {
    ctx_frame *f;
    __asm__("movl ctx_thread_frames_slot(%%rip), %k0; movq %%gs:0x1480(,%0,8), %0" : "=r"(f));
    return f;
}
static inline void ctx_thread_frames_set(ctx_frame *f) {
    uint64_t slot;
    // volatile: it is for its store, and its output isn't used
    __asm__ volatile("movl ctx_thread_frames_slot(%%rip), %k0; movq %1, %%gs:0x1480(,%0,8)" : "=&r"(slot) : "r"(f));
}
#define CTX_FRAMES_GET() ctx_thread_frames_get()
#define CTX_FRAMES_SET(f) ctx_thread_frames_set(f)
#else
extern _Thread_local ctx_thread *ctx_thread_current;
extern _Thread_local uint64_t ctx_thread_limit;
extern _Thread_local ctx_frame *ctx_thread_frames;
#define CTX_HERE ctx_thread_current
#define CTX_STACK_LIMIT ctx_thread_limit
#define CTX_STACK_LIMIT_NOW() ctx_thread_limit
#define CTX_FRAMES_GET() ctx_thread_frames
#define CTX_FRAMES_SET(f) (ctx_thread_frames = (f))
#endif
// C's main calls it first: the main thread's state, and locks in the runtime.
void ctx_thread_setup(void);
// A callback's: gives the calling thread t if it has no state, and returns whether it did; then
// ctx_thread_leave(t) takes it back, after the fn std's start gave for a thread's end.
int ctx_thread_enter(ctx_thread *t);
void ctx_thread_leave(ctx_thread *t);
// std's thread::begin, on a new thread: its stack limit, `usable` bytes below the caller's
// frame, and its name, cut to 63 bytes.
void ctx_thread_begin(uint64_t usable, ctx_slice name);
void ctx_thread_rename(ctx_slice name);
// std's rt::thread_runs: the record of the task the calling thread runs from here on, or null
// for none, for a panic's call path, which ends with where the task was started.
void ctx_thread_task(void *record);
#else
#define CTX_HERE (&ctx_main_thread)
#define CTX_STACK_LIMIT (ctx_main_thread.stack_limit)
#define CTX_STACK_LIMIT_NOW() (ctx_main_thread.stack_limit)
#define CTX_FRAMES_GET() (ctx_main_thread.frames)
#define CTX_FRAMES_SET(f) (ctx_main_thread.frames = (f))
#endif

// The calling thread's name, for a panic's report: empty for the main thread (std's rt).
ctx_slice ctx_here_name(void);
// The fn the runtime calls when a thread it gave state to ends, std's start's (std/rt.ctx): it
// writes out the thread's standard output.
typedef void (*ctx_end_fn)(void);
void ctx_ends_set(ctx_end_fn ends);

// ctxrt.c's, for ctxthread.c: the calling thread's state, which its setup makes CTX_HERE's;
// whether the program is threaded, which turns ctxrt.c's lock on; the fn std's start gave for
// a thread's end; where an ending thread's records go; and the calling thread's frame that last
// called C, which its setup makes CTX_FRAMES_GET's and CTX_FRAMES_SET's.
extern ctx_thread *(*ctx_current)(void);
extern int ctx_threaded;
extern ctx_end_fn ctx_thread_ends;
void ctx_rec_give(ctx_thread *t);
extern ctx_frame *(*ctx_frames_now)(void);
extern void (*ctx_frames_put)(ctx_frame *f);

// ---- call paths
//
// A panic's call path (spec §15, Call paths). Every function takes its caller's frame as its
// first parameter (CTX_UP), and one that calls has a frame of its own in its C frame (CTX_FRAME,
// after the stack check): its caller's, its ctx_where, and where its last call is, which it
// notes before each call (CTX_AT) and passes to what it calls (CTX_ME). Nothing is linked
// through memory that outlives the call, and nothing is undone when it returns, so a function
// that C inlines with all it calls keeps no frame at all. A function that calls nothing has
// none. A panic passes its position, its function's ctx_where and that function's caller's frame
// (CTX_UPV), from which the runtime reads the path.
//
// C code between two functions of the program has no frame. Before a call of C (an extern fn's
// eN, or a C function pointer), the calling thread notes the frame that calls (CTX_OUT), and a
// callback's C function starts from it, with a frame that says C called it (CTX_C_FRAME), and
// notes it again when it returns: so a callback's path goes on into the function that called
// the C, and a native's panic without a position has that function's path. On a thread the
// program didn't start, a callback's is the first frame.
//
// Compiled with CTX_NO_PATH, a program passes and keeps no frames, and a panic's path is the
// function it is in.

static inline void ctx_frame_back(ctx_frame *f) { CTX_FRAMES_SET(f->up); }
#ifndef CTX_NO_PATH
#define CTX_UP ctx_frame *_up,
#define CTX_UP0 ctx_frame *_up
#define CTX_UPV _up
#define CTX_FRAME(where) ctx_frame _ctx_frame; _ctx_frame.up = _up; _ctx_frame.in = (where)
// One store for each call: a second one cost the script VM of a game 13% of its time, and this 4%.
#define CTX_AT(l, c) (_ctx_frame.at = (uint32_t)(l) | (uint32_t)(c) << 20)
#define CTX_ME &_ctx_frame,
#define CTX_ME0 &_ctx_frame
// What code that is no function of the program's passes on: a function value's code, its
// caller's frame; C's main, none.
#define CTX_PASS _up,
#define CTX_PASS0 _up
#define CTX_NONE (ctx_frame *)0,
#define CTX_NONE0 (ctx_frame *)0
#define CTX_OUT() CTX_FRAMES_SET(&_ctx_frame)
#define CTX_OUT_UP() CTX_FRAMES_SET(_up)
#define CTX_C_FRAME ctx_frame _ctx_frame __attribute__((cleanup(ctx_frame_back))) = { CTX_FRAMES_GET(), &ctx_c_code, 0 }
#define CTX_BACK() CTX_FRAMES_SET(_ctx_frame.up)
#else
#define CTX_UP
#define CTX_UP0 void
#define CTX_UPV ((ctx_frame *)0)
#define CTX_FRAME(where) (void)0
#define CTX_AT(l, c) ((void)0)
#define CTX_ME
#define CTX_ME0
#define CTX_PASS
#define CTX_PASS0
#define CTX_NONE
#define CTX_NONE0
#define CTX_OUT() ((void)0)
#define CTX_OUT_UP() ((void)0)
#define CTX_C_FRAME (void)0
#define CTX_BACK() ((void)0)
#endif

// What a callback's frame is in: C code, which called it.
extern const ctx_where ctx_c_code;

// std's rt::Frame, one entry of a path: a function's name, its file ("" if it has none) and the
// position in it (line 0 if it isn't known), and its kind: 0 a call, 1 C code that called a
// callback (no name, file or position), 2 where the thread's task was started.
typedef struct { ctx_slice name; ctx_slice file; uint32_t line, col, kind; } ctx_path_entry;
// std's rt::count_frames and rt::get_frame: the calling thread's path, innermost first: of the
// panic it reports, or else of the caller, whose own call of these is entry 0.
uint64_t ctx_path_count(void);
ctx_path_entry ctx_path_frame(uint64_t index);

// ---- stack

// A frame below `limit`, the program's `#stack_limit` static (spec §15, rule 13), panics with
// "stack overflow". std's start sets it; 0 checks nothing.
#define CTX_STACK_CHECK_AT(limit) \
    do { if ((uint64_t)(uintptr_t)__builtin_frame_address(0) < (limit)) ctx_stack_overflow(CTX_UPV); } while (0)
// The check against the `#stack_limit` static, CTX_STACK_LIMIT: the calling thread's (above).
#define CTX_STACK_CHECK() CTX_STACK_CHECK_AT(CTX_STACK_LIMIT_NOW())

// ---- function values
//
// Every function value, bound or not, points to a record whose first member is its code. The
// code takes the record, then the function type's fields in name order (`mut` ones as void*).
// A named function's record is static. A bind's record is in its function's frame when no
// earlier record of the same bind can still be called when it runs again (ctxc/emit_c.ctx,
// Records); otherwise it is borrowed from a stack that the function restores on return.

typedef struct ctx_fn { void (*code)(void); } ctx_fn;
typedef struct { ctx_fn base; ctx_fn *inner; } ctx_adapter;

// Where the runtime takes memory for records from once its own is used up (64 KiB for
// borrowed records, 16 KiB for permanent ones): pages of at least `size` bytes that last until
// the program ends, or null; `size` is a multiple of 4096. std's start sets it (std/rt.ctx).
// It may make no record: one that needs more pages traps. Without it, a record past the
// runtime's own panics.
typedef void *(*ctx_pages_fn)(uint64_t size);
void ctx_pages_set(ctx_pages_fn pages);

// Borrowed records: `CTX_RECORDS;` at the top of a function that may make one, which
// restores the stack's top when the function returns, after its defers. Each thread has its
// own stack of them (ctx_thread).
#define ctx_recs (CTX_HERE->recs)
void *ctx_rec_more(ctx_thread *t, uint64_t n);
static inline void ctx_rec_release(ctx_rec_mark *m) { ctx_recs = *m; }
#define CTX_RECORDS ctx_rec_mark _ctx_records __attribute__((cleanup(ctx_rec_release))) = ctx_recs

// n bytes, not zeroed, until the function's CTX_RECORDS restores the top.
static inline void *ctx_rec_alloc(uint64_t n) {
    ctx_thread *t = CTX_HERE;
    n = (n + 15) & ~(uint64_t)15;
    char *p = t->recs.top;
    if ((uint64_t)(t->recs.end - p) < n) return ctx_rec_more(t, n);
    t->recs.top = p + n;
    return p;
}

void *ctx_alloc(size_t n);                 // permanent storage, not zeroed
// The adapter of `fn` value `inner` with `code`: the same record for the same pair.
ctx_fn *ctx_adapt(ctx_fn *inner, void (*code)(void));

// A task's record (spec §15, Tasks): a bind written as a start's `run`, whose record holds its
// size after its code, so that the task's backend can copy it (@record_size, @record_copy).
// After them, where it was started: the function, and the start's position in it.
typedef struct { ctx_fn base; uint64_t size; ctx_slice name; const ctx_where *in; uint32_t line, col; } ctx_task_rec;
// The name of the task fn whose record rec is, or a copy of one.
ctx_slice ctx_task_name(void *rec);
// Copies record `rec` into `into`, which holds at least `len` bytes: a panic if they're fewer.
void ctx_rec_copy(void *into, uint64_t len, ctx_fn *rec);

// ---- integer arithmetic

#define CTX_OVERFLOW() ctx_panic(line, col, in, up, "integer overflow")

#define CTX_INT_OPS(T, S, MIN, SIGNED)                                                            \
    static inline T ctx_add_##S(T a, T b, CTX_POS) { T r; if (__builtin_add_overflow(a, b, &r)) CTX_OVERFLOW(); return r; } \
    static inline T ctx_sub_##S(T a, T b, CTX_POS) { T r; if (__builtin_sub_overflow(a, b, &r)) CTX_OVERFLOW(); return r; } \
    static inline T ctx_mul_##S(T a, T b, CTX_POS) { T r; if (__builtin_mul_overflow(a, b, &r)) CTX_OVERFLOW(); return r; } \
    static inline T ctx_div_##S(T a, T b, CTX_POS) {                                              \
        if (b == 0) ctx_panic(line, col, in, up, "division by zero");                             \
        if (SIGNED && a == (T)(MIN) && b == (T)-1) CTX_OVERFLOW();                                \
        return a / b;                                                                             \
    }                                                                                             \
    static inline T ctx_rem_##S(T a, T b, CTX_POS) {                                              \
        if (b == 0) ctx_panic(line, col, in, up, "division by zero");                             \
        if (SIGNED && b == (T)-1) return 0;                                                       \
        return a % b;                                                                             \
    }                                                                                             \
    static inline T ctx_neg_##S(T a, CTX_POS) { T r; if (__builtin_sub_overflow((T)0, a, &r)) CTX_OVERFLOW(); return r; } \
    /* a / b into *r, or 1 if it overflows (an `ifoverflow` covers it): still a panic for 0 */  \
    static inline int ctx_div_ovf_##S(T a, T b, T *r, CTX_POS) {                                 \
        if (b == 0) ctx_panic(line, col, in, up, "division by zero");                             \
        if (SIGNED && a == (T)(MIN) && b == (T)-1) return 1;                                      \
        *r = a / b;                                                                               \
        return 0;                                                                                 \
    }                                                                                             \
    /* a << n, n checked: a * 2^n, so it overflows where shifting back doesn't give a */           \
    static inline T ctx_shl_##S(T a, int n, CTX_POS) { T r = (T)((uint64_t)a << n); if ((T)(r >> n) != a) CTX_OVERFLOW(); return r; }

CTX_INT_OPS(int8_t, i8, INT8_MIN, 1)
CTX_INT_OPS(int16_t, i16, INT16_MIN, 1)
CTX_INT_OPS(int32_t, i32, INT32_MIN, 1)
CTX_INT_OPS(int64_t, i64, INT64_MIN, 1)
CTX_INT_OPS(uint8_t, u8, 0, 0)
CTX_INT_OPS(uint16_t, u16, 0, 0)
CTX_INT_OPS(uint32_t, u32, 0, 0)
CTX_INT_OPS(uint64_t, u64, 0, 0)

// A shift count, checked against the width of the value shifted.
static inline int ctx_shcount_i(int64_t n, int bits, CTX_POS) {
    if (n < 0 || n >= bits) ctx_panic_shift_s(n, bits, line, col, in, up);
    return (int)n;
}
static inline int ctx_shcount_u(uint64_t n, int bits, CTX_POS) {
    if (n >= (uint64_t)bits) ctx_panic_shift_u(n, bits, line, col, in, up);
    return (int)n;
}

// An array index, checked against the length.
static inline uint64_t ctx_idx(uint64_t i, uint64_t n, CTX_POS) {
    if (i >= n) ctx_panic_index(i, n, line, col, in, up);
    return i;
}

// A slice's sub-range lo..hi, or "range LO..HI out of bounds for length N".
static inline void ctx_range(uint64_t lo, uint64_t hi, uint64_t n, CTX_POS) {
    if (lo > hi || hi > n) ctx_panic_range(lo, hi, n, line, col, in, up);
}

// The same for an index, or bounds, of a signed type (spec §12, Arrays, rule 1), converted to 64
// bits as C converts it: one below 0 is then past any length, so the one unsigned compare
// rejects it too. The panic shows it signed; sg says which bounds are (1: lo, 2: hi).
static inline uint64_t ctx_idx_s(uint64_t i, uint64_t n, CTX_POS) {
    if (i >= n) ctx_panic_index_s((int64_t)i, n, line, col, in, up);
    return i;
}

static inline void ctx_range_s(uint64_t lo, uint64_t hi, uint64_t n, int sg, CTX_POS) {
    if (lo > hi || hi > n) ctx_panic_range_s(lo, hi, n, sg, line, col, in, up);
}

// ---- @as

// Whether an integer is in [lo, hi]: what an `ifoverflow` that covers the @as tests.
static inline int ctx_fits_s(int64_t v, int64_t lo, int64_t hi) { return v >= lo && v <= hi; }
static inline int ctx_fits_u(uint64_t v, uint64_t hi) { return v <= hi; }

// An integer into [lo, hi], or "@as: V is not representable in DST".
static inline int64_t ctx_as_s(int64_t v, int64_t lo, int64_t hi, const char *dst, CTX_POS) {
    if (!ctx_fits_s(v, lo, hi)) ctx_panic_as_s(v, dst, line, col, in, up);
    return v;
}

static inline uint64_t ctx_as_u(uint64_t v, uint64_t hi, const char *dst, CTX_POS) {
    if (!ctx_fits_u(v, hi)) ctx_panic_as_u(v, dst, line, col, in, up);
    return v;
}

// A float, truncated toward zero, into [lo, hi]. NaN and infinities panic. Keep the checks
// visible to the caller's optimizer; only a failed conversion needs the runtime's number
// formatting and diagnostics.
// Whether trunc(v) is in [lo, hi], or [0, hi]: false for NaN and the infinities.
static inline int ctx_f2i_fits_s(double v, int64_t lo, int64_t hi) {
    // Is trunc(v) at least lo? lo - 1 is exact except for INT64_MIN, with no double between
    // INT64_MIN - 1 and INT64_MIN. The comparisons also reject NaN before the C cast.
    int low_ok = lo == INT64_MIN ? v >= -9223372036854775808.0 : v > (double)lo - 1.0;
    return low_ok && v < (double)hi + 1.0;
}

static inline int ctx_f2i_fits_u(double v, uint64_t hi) {
    // hi + 1 is 2^8, 2^16, 2^32 or 2^64: exact as a double. Values in (-1, 0) truncate to 0.
    double limit = hi == UINT64_MAX ? 18446744073709551616.0 : (double)hi + 1.0;
    return v > -1.0 && v < limit;
}

static inline int64_t ctx_f2i_s(double v, int64_t lo, int64_t hi, const char *dst, CTX_POS) {
    if (!ctx_f2i_fits_s(v, lo, hi)) ctx_f2i_fail(v, dst, line, col, in, up);
    return (int64_t)v;
}

static inline uint64_t ctx_f2i_u(double v, uint64_t hi, const char *dst, CTX_POS) {
    if (!ctx_f2i_fits_u(v, hi)) ctx_f2i_fail(v, dst, line, col, in, up);
    return (uint64_t)v;
}

#endif
