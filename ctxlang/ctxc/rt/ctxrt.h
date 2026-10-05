// ctxrt: the runtime for C that ctxc emits. Needs GNU C (statement expressions, __typeof__,
// overflow builtins, empty structs) on a 64-bit little-endian target.
//
// It is what the C needs that ctxlang can't say itself: the checks the C calls, panics, and
// function values' records. It keeps no state of std's: that is std's statics (spec §15, rule
// 13), the stack check's limit among them. The rest is std's, in ctxlang: starting the program
// (a `#start` fn, std/rt.ctx), reporting a panic (a `#panic` fn), and the platform's layer
// (std/os), which the natives of std are over.
// ctxrt.c calls no C library function. Floats as text and back, which std's
// ascii declares, are ctxfloat.c's, which a program links only if it uses them (ctxc/drive.ctx).

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
// off first, so that a stack overflow can be reported); a panic while one is reported, or a panic fn that returns, traps. `file` is FNV-1a of
// the file's name with the top bit set, which names it in the program's file table, or an index
// into that table; an empty name stands for the program's path.

_Noreturn void ctx_panic(uint32_t line, uint32_t col, uint32_t file, const char *msg);
// A panic without a position, such as a native's.
_Noreturn void ctx_panic_nopos(const char *msg);
// std's rt::fail: a panic without a position, whose message isn't a C string.
_Noreturn void ctx_panic_msg(ctx_slice msg);

#define CTX_POS uint32_t line, uint32_t col, uint32_t file

// The checks' messages, with their numbers: "index I out of bounds for length N" and the rest.
_Noreturn void ctx_panic_index(uint64_t i, uint64_t n, CTX_POS);
_Noreturn void ctx_panic_range(uint64_t lo, uint64_t hi, uint64_t n, CTX_POS);
_Noreturn void ctx_panic_shift_s(int64_t n, int bits, CTX_POS);
_Noreturn void ctx_panic_shift_u(uint64_t n, int bits, CTX_POS);
_Noreturn void ctx_panic_as_s(int64_t v, const char *dst, CTX_POS);
_Noreturn void ctx_panic_as_u(uint64_t v, const char *dst, CTX_POS);
// A float that isn't representable, in Python's repr: ctxfloat.c's, which writes floats.
_Noreturn void ctx_f2i_fail(double v, const char *dst, CTX_POS);

// ---- stack

// A frame below `limit`, the program's `#stack_limit` static (spec §15, rule 13), panics with
// "stack overflow". std's start sets it; 0 checks nothing.
#define CTX_STACK_CHECK_AT(limit) \
    do { if ((uint64_t)(uintptr_t)__builtin_frame_address(0) < (limit)) ctx_panic_nopos("stack overflow"); } while (0)

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
// restores the stack's top when the function returns, after its defers.
typedef struct ctx_rec_seg { struct ctx_rec_seg *next; char *data; char *end; } ctx_rec_seg;
typedef struct { ctx_rec_seg *seg; char *top; char *end; } ctx_rec_mark;
extern ctx_rec_mark ctx_recs;
void *ctx_rec_more(uint64_t n);
static inline void ctx_rec_release(ctx_rec_mark *m) { ctx_recs = *m; }
#define CTX_RECORDS ctx_rec_mark _ctx_records __attribute__((cleanup(ctx_rec_release))) = ctx_recs

// n bytes, not zeroed, until the function's CTX_RECORDS restores the top.
static inline void *ctx_rec_alloc(uint64_t n) {
    n = (n + 15) & ~(uint64_t)15;
    char *p = ctx_recs.top;
    if ((uint64_t)(ctx_recs.end - p) < n) return ctx_rec_more(n);
    ctx_recs.top = p + n;
    return p;
}

void *ctx_alloc(size_t n);                 // permanent storage, not zeroed
// The adapter of `fn` value `inner` with `code`: the same record for the same pair.
ctx_fn *ctx_adapt(ctx_fn *inner, void (*code)(void));

// ---- integer arithmetic

#define CTX_OVERFLOW() ctx_panic(line, col, file, "integer overflow")

#define CTX_INT_OPS(T, S, MIN, SIGNED)                                                            \
    static inline T ctx_add_##S(T a, T b, CTX_POS) { T r; if (__builtin_add_overflow(a, b, &r)) CTX_OVERFLOW(); return r; } \
    static inline T ctx_sub_##S(T a, T b, CTX_POS) { T r; if (__builtin_sub_overflow(a, b, &r)) CTX_OVERFLOW(); return r; } \
    static inline T ctx_mul_##S(T a, T b, CTX_POS) { T r; if (__builtin_mul_overflow(a, b, &r)) CTX_OVERFLOW(); return r; } \
    static inline T ctx_div_##S(T a, T b, CTX_POS) {                                              \
        if (b == 0) ctx_panic(line, col, file, "division by zero");                             \
        if (SIGNED && a == (T)(MIN) && b == (T)-1) CTX_OVERFLOW();                                \
        return a / b;                                                                             \
    }                                                                                             \
    static inline T ctx_rem_##S(T a, T b, CTX_POS) {                                              \
        if (b == 0) ctx_panic(line, col, file, "division by zero");                             \
        if (SIGNED && b == (T)-1) return 0;                                                       \
        return a % b;                                                                             \
    }                                                                                             \
    static inline T ctx_neg_##S(T a, CTX_POS) { T r; if (__builtin_sub_overflow((T)0, a, &r)) CTX_OVERFLOW(); return r; }

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
    if (n < 0 || n >= bits) ctx_panic_shift_s(n, bits, line, col, file);
    return (int)n;
}
static inline int ctx_shcount_u(uint64_t n, int bits, CTX_POS) {
    if (n >= (uint64_t)bits) ctx_panic_shift_u(n, bits, line, col, file);
    return (int)n;
}

// An array index, checked against the length.
static inline uint64_t ctx_idx(uint64_t i, uint64_t n, CTX_POS) {
    if (i >= n) ctx_panic_index(i, n, line, col, file);
    return i;
}

// A slice's sub-range lo..hi, or "range LO..HI out of bounds for length N".
static inline void ctx_range(uint64_t lo, uint64_t hi, uint64_t n, CTX_POS) {
    if (lo > hi || hi > n) ctx_panic_range(lo, hi, n, line, col, file);
}

// ---- @as

// An integer into [lo, hi], or "@as: V is not representable in DST".
static inline int64_t ctx_as_s(int64_t v, int64_t lo, int64_t hi, const char *dst, CTX_POS) {
    if (v < lo || v > hi) ctx_panic_as_s(v, dst, line, col, file);
    return v;
}

static inline uint64_t ctx_as_u(uint64_t v, uint64_t hi, const char *dst, CTX_POS) {
    if (v > hi) ctx_panic_as_u(v, dst, line, col, file);
    return v;
}

// A float, truncated toward zero, into [lo, hi]. NaN and infinities panic. Keep the checks
// visible to the caller's optimizer; only a failed conversion needs the runtime's number
// formatting and diagnostics.
static inline int64_t ctx_f2i_s(double v, int64_t lo, int64_t hi, const char *dst, CTX_POS) {
    // Is trunc(v) at least lo? lo - 1 is exact except for INT64_MIN, with no double between
    // INT64_MIN - 1 and INT64_MIN. The comparisons also reject NaN before the C cast.
    int low_ok = lo == INT64_MIN ? v >= -9223372036854775808.0 : v > (double)lo - 1.0;
    if (!(low_ok && v < (double)hi + 1.0)) ctx_f2i_fail(v, dst, line, col, file);
    return (int64_t)v;
}

static inline uint64_t ctx_f2i_u(double v, uint64_t hi, const char *dst, CTX_POS) {
    // hi + 1 is 2^8, 2^16, 2^32 or 2^64: exact as a double. Values in (-1, 0) truncate to 0.
    double limit = hi == UINT64_MAX ? 18446744073709551616.0 : (double)hi + 1.0;
    if (!(v > -1.0 && v < limit)) ctx_f2i_fail(v, dst, line, col, file);
    return (uint64_t)v;
}

#endif
