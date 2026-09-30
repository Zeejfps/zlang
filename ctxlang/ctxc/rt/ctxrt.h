// ctxrt: the runtime for C that ctxc emits. Needs GNU C (statement expressions, __typeof__,
// overflow builtins, empty structs) on a 64-bit little-endian target.
//
// Everything that doesn't depend on a program's types lives here: panics, checked arithmetic,
// conversions, bounds checks, closures and the natives. Messages match ctxi's word for word.

#ifndef CTXRT_H
#define CTXRT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

_Static_assert(sizeof(void *) == 8, "ctxrt needs 64-bit pointers");

// ---- panics

// Prints "FILE:LINE:COL: panic: MSG" to standard error and exits with 134. `file` indexes the
// program's file table; an empty name stands for the program's own path.
_Noreturn void ctx_panic(uint32_t line, uint32_t col, uint32_t file, const char *msg);
// A panic without a position, such as a native's: "PROGRAM: panic: MSG".
_Noreturn void ctx_panic_nopos(const char *msg);
_Noreturn void ctx_panic_fmt(uint32_t line, uint32_t col, uint32_t file, const char *fmt, ...);

// ---- stack

extern char *ctx_stack_limit;
#define CTX_STACK_CHECK() \
    do { if ((char *)__builtin_frame_address(0) < ctx_stack_limit) ctx_panic_nopos("stack overflow"); } while (0)

// ---- startup

typedef struct { uint32_t tag; void *ptr; uint64_t len; } ctx_slice;   // slice::Slice(T)

// `program` is the program's path, for panics in files named "": CTX_PROGRAM_NAME, which the
// generated code's includer can define.
void ctx_init(const char *const *files, uint32_t nfiles, const char *program, int argc, char **argv);
#ifndef CTX_PROGRAM_NAME
#define CTX_PROGRAM_NAME "program"
#endif
ctx_slice ctx_args(void);                  // main's `args`: a Slice(Slice(u8)) of UTF-8 bytes
int ctx_exit(int32_t code);                // flushes output, closes files; returns code

#define CTX_BITCAST(T, x) ({ __typeof__(x) _bc_v = (x); T _bc_r; \
    _Static_assert(sizeof(_bc_r) == sizeof(_bc_v), "bitcast size"); memcpy(&_bc_r, &_bc_v, sizeof _bc_r); _bc_r; })

// ---- function values
//
// Every function value, bound or not, points to a record whose first member is its code. The
// code takes the record, then the function type's fields in name order (`mut` ones as void*).

typedef struct ctx_fn { void (*code)(void); } ctx_fn;
typedef struct { ctx_fn base; ctx_fn *inner; } ctx_adapter;

void *ctx_alloc(size_t n);                 // zeroed, never freed, like ctxi's bound functions
static inline ctx_fn *ctx_adapt(ctx_fn *inner, void (*code)(void)) {
    ctx_adapter *a = ctx_alloc(sizeof *a);
    a->base.code = code;
    a->inner = inner;
    return &a->base;
}

// ---- integer arithmetic

#define CTX_POS uint32_t line, uint32_t col, uint32_t file
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

// An array index, checked against the length.
static inline uint64_t ctx_idx(uint64_t i, uint64_t n, CTX_POS) {
    if (i >= n) ctx_panic_fmt(line, col, file, "index %llu out of bounds for length %llu",
                              (unsigned long long)i, (unsigned long long)n);
    return i;
}

// ---- @as

// An integer into [lo, hi], or "@as: V is not representable in DST".
int64_t ctx_as_s(int64_t v, int64_t lo, int64_t hi, const char *dst, CTX_POS);
uint64_t ctx_as_u(uint64_t v, uint64_t hi, const char *dst, CTX_POS);
// A float, truncated toward zero, into [lo, hi]. NaN and infinities panic.
int64_t ctx_f2i_s(double v, int64_t lo, int64_t hi, const char *dst, CTX_POS);
uint64_t ctx_f2i_u(double v, uint64_t hi, const char *dst, CTX_POS);

// ---- natives (std's runtime-provided functions)

void ctx_n_io_write(void *io, uint32_t to, ctx_slice bytes);
uint64_t ctx_n_io_read(void *io, ctx_slice into);
uint64_t ctx_n_ascii_f64_digits(double n, ctx_slice into);
uint64_t ctx_n_ascii_f32_digits(float n, ctx_slice into);
double ctx_n_ascii_f64_parse(ctx_slice text);
float ctx_n_ascii_f32_parse(ctx_slice text);
int64_t ctx_n_fs_sys_open(void *fs, ctx_slice path, uint8_t mode);
int64_t ctx_n_fs_sys_read(void *fs, uint32_t file, ctx_slice into);
int64_t ctx_n_fs_sys_write(void *fs, uint32_t file, ctx_slice bytes);
int64_t ctx_n_fs_sys_close(void *fs, uint32_t file);
int64_t ctx_n_fs_sys_size(void *fs, ctx_slice path);
int64_t ctx_n_fs_sys_remove(void *fs, ctx_slice path);
ctx_slice ctx_n_mem_sys_pages(void *mem, uint64_t size);

#endif
