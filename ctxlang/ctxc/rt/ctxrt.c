// ctxrt: see ctxrt.h. Written against mingw-w64 (Windows) and POSIX.

#define __USE_MINGW_ANSI_STDIO 1     // C99 printf: two-digit exponents, %llu
#include "ctxrt.h"

#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>

#ifdef _WIN32
#include <io.h>
#include <windows.h>
#define ctx_strtod __mingw_strtod     // correctly rounded, unlike msvcrt's
#define ctx_strtof __mingw_strtof
#else
#include <sys/resource.h>
#include <unistd.h>
#define ctx_strtod strtod
#define ctx_strtof strtof
#define O_BINARY 0
#endif

static const char *program_name = "program";
static const char *const *ctx_files;
static uint32_t ctx_nfiles;
char *ctx_stack_limit;

// ---- output: standard output is buffered and flushed before anything else is written or read

static char out_buf[1 << 16];
static size_t out_len;

static void write_all(int fd, const void *p, size_t n) {
    const char *c = p;
    while (n > 0) {
#ifdef _WIN32
        int w = _write(fd, c, n > 0x40000000 ? 0x40000000 : (unsigned)n);
#else
        ssize_t w = write(fd, c, n);
#endif
        if (w <= 0) return;
        c += w;
        n -= (size_t)w;
    }
}

static void flush_out(void) {
    write_all(1, out_buf, out_len);
    out_len = 0;
}

static void put_out(const void *p, size_t n) {
    if (out_len + n > sizeof out_buf) flush_out();
    if (n > sizeof out_buf) { write_all(1, p, n); return; }
    memcpy(out_buf + out_len, p, n);
    out_len += n;
}

static void put_err(const char *s) {
    flush_out();
    write_all(2, s, strlen(s));
}

// ---- panics

static const char *file_name(uint32_t file) {
    if (file < ctx_nfiles && ctx_files[file][0]) return ctx_files[file];
    return program_name;
}

_Noreturn static void die(const char *where, const char *msg) {
    char buf[4096];
    snprintf(buf, sizeof buf, "%s: panic: %s\n", where, msg);
    put_err(buf);
    exit(134);
}

_Noreturn void ctx_panic(uint32_t line, uint32_t col, uint32_t file, const char *msg) {
    char where[1024];
    snprintf(where, sizeof where, "%s:%u:%u", file_name(file), (unsigned)line, (unsigned)col);
    die(where, msg);
}

_Noreturn void ctx_panic_nopos(const char *msg) {
    die(program_name, msg);
}

_Noreturn void ctx_panic_fmt(uint32_t line, uint32_t col, uint32_t file, const char *fmt, ...) {
    char msg[2048];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(msg, sizeof msg, fmt, ap);
    va_end(ap);
    ctx_panic(line, col, file, msg);
}

// ---- memory for closures: a bump allocator over chunks that are never freed

void *ctx_alloc(size_t n) {
    static char *chunk;
    static size_t left;
    n = (n + 15) & ~(size_t)15;
    if (n > left) {
        size_t size = n > (1 << 20) ? n : (1 << 20);
        chunk = calloc(1, size);
        if (!chunk) ctx_panic_nopos("out of memory");
        left = size;
    }
    void *p = chunk;
    chunk += n;
    left -= n;
    return p;
}

// ---- floats as text, exactly as Python writes them (ctxi's f64_digits and f32_digits)

// repr(v) for a double, with ".0" added to whole numbers: shortest digits that read back as v,
// in exponent form when the decimal exponent is below -4 or above 15.
static int repr_f64(double v, char *out) {
    if (isnan(v)) return sprintf(out, "nan");
    if (isinf(v)) return sprintf(out, v < 0 ? "-inf" : "inf");
    if (v == 0) return sprintf(out, signbit(v) ? "-0.0" : "0.0");
    char buf[64];
    int p;
    for (p = 1; p < 17; p++) {
        snprintf(buf, sizeof buf, "%.*e", p - 1, v);
        if (ctx_strtod(buf, NULL) == v) break;
    }
    snprintf(buf, sizeof buf, "%.*e", p - 1, v);
    // buf is [-]D[.DDD]e[+-]XX
    char digits[32];
    int nd = 0, i = 0, neg = 0;
    if (buf[i] == '-') { neg = 1; i++; }
    for (; buf[i] != 'e'; i++)
        if (buf[i] != '.') digits[nd++] = buf[i];
    while (nd > 1 && digits[nd - 1] == '0') nd--;
    int exp = atoi(buf + i + 1);
    int decpt = exp + 1;
    char *o = out;
    if (neg) *o++ = '-';
    if (decpt <= -4 || decpt > 16) {
        *o++ = digits[0];
        if (nd > 1) {
            *o++ = '.';
            memcpy(o, digits + 1, nd - 1);
            o += nd - 1;
        }
        o += sprintf(o, "e%c%02d", exp < 0 ? '-' : '+', exp < 0 ? -exp : exp);
    } else if (decpt <= 0) {
        *o++ = '0';
        *o++ = '.';
        for (int k = 0; k < -decpt; k++) *o++ = '0';
        memcpy(o, digits, nd);
        o += nd;
    } else if (decpt >= nd) {
        memcpy(o, digits, nd);
        o += nd;
        for (int k = 0; k < decpt - nd; k++) *o++ = '0';
        *o++ = '.';
        *o++ = '0';
    } else {
        memcpy(o, digits, decpt);
        o += decpt;
        *o++ = '.';
        memcpy(o, digits + decpt, nd - decpt);
        o += nd - decpt;
    }
    *o = 0;
    return (int)(o - out);
}

// The shortest '%.Ng' text that reads back as v through a double, as ctxi's _shortest_f32, plus
// ".0" if it has neither '.' nor 'e'.
static int repr_f32(float v, char *out) {
    if (isnan(v)) return sprintf(out, "nan");
    if (isinf(v)) return sprintf(out, v < 0 ? "-inf" : "inf");
    int p, n = 0;
    for (p = 1; p <= 9; p++) {
        n = snprintf(out, 64, "%.*g", p, (double)v);
        if ((float)ctx_strtod(out, NULL) == v) break;
    }
    if (p > 9) n = snprintf(out, 64, "%.9g", (double)v);
    if (!strchr(out, '.') && !strchr(out, 'e')) {
        strcpy(out + n, ".0");
        n += 2;
    }
    return n;
}

static uint64_t put_digits(const char *text, int n, ctx_slice into) {
    if ((uint64_t)n > into.len) {
        char msg[128];
        snprintf(msg, sizeof msg, "%d characters do not fit in a buffer of %llu", n, (unsigned long long)into.len);
        ctx_panic_nopos(msg);
    }
    memcpy(into.ptr, text, n);
    return (uint64_t)n;
}

uint64_t ctx_ascii_f64_digits(double v, ctx_slice into) {
    char buf[64];
    return put_digits(buf, repr_f64(v, buf), into);
}

uint64_t ctx_ascii_f32_digits(float v, ctx_slice into) {
    char buf[64];
    return put_digits(buf, repr_f32(v, buf), into);
}

static char *c_string(ctx_slice s) {
    char *p = malloc(s.len + 1);
    if (!p) ctx_panic_nopos("out of memory");
    if (s.len) memcpy(p, s.ptr, s.len);
    p[s.len] = 0;
    return p;
}

double ctx_ascii_f64_parse(ctx_slice text) {
    char *s = c_string(text);
    double v = ctx_strtod(s, NULL);
    free(s);
    return v;
}

float ctx_ascii_f32_parse(ctx_slice text) {
    char *s = c_string(text);
    float v = ctx_strtof(s, NULL);
    free(s);
    return v;
}

// ---- @as

int64_t ctx_as_s(int64_t v, int64_t lo, int64_t hi, const char *dst, CTX_POS) {
    if (v < lo || v > hi)
        ctx_panic_fmt(line, col, file, "@as: %lld is not representable in %s", (long long)v, dst);
    return v;
}

uint64_t ctx_as_u(uint64_t v, uint64_t hi, const char *dst, CTX_POS) {
    if (v > hi)
        ctx_panic_fmt(line, col, file, "@as: %llu is not representable in %s", (unsigned long long)v, dst);
    return v;
}

_Noreturn static void f2i_fail(double v, const char *dst, CTX_POS) {
    char text[64];
    repr_f64(v, text);
    ctx_panic_fmt(line, col, file, "@as: %s is not representable in %s", text, dst);
}

// Is trunc(v) at least lo? Exact: lo - 1 is a double for every lo but INT64_MIN, and no double
// lies strictly between INT64_MIN - 1 and INT64_MIN.
static int at_least(double v, int64_t lo) {
    return lo == INT64_MIN ? v >= -9223372036854775808.0 : v > (double)lo - 1.0;
}

int64_t ctx_f2i_s(double v, int64_t lo, int64_t hi, const char *dst, CTX_POS) {
    if (!(at_least(v, lo) && v < (double)hi + 1.0)) f2i_fail(v, dst, line, col, file);
    return (int64_t)v;
}

uint64_t ctx_f2i_u(double v, uint64_t hi, const char *dst, CTX_POS) {
    // hi + 1 is 2^8, 2^16, 2^32 or 2^64: exact as a double.
    double limit = hi == UINT64_MAX ? 18446744073709551616.0 : (double)hi + 1.0;
    if (!(v > -1.0 && v < limit)) f2i_fail(v, dst, line, col, file);
    return (uint64_t)v;
}

// ---- io

void ctx_io_write(uint32_t to, ctx_slice bytes) {
    if (bytes.len == 0) return;
    if (to == 0) {
        put_out(bytes.ptr, bytes.len);
    } else {
        flush_out();
        write_all(2, bytes.ptr, bytes.len);
    }
}

uint64_t ctx_io_read(ctx_slice into) {
    if (into.len == 0) return 0;
    flush_out();
#ifdef _WIN32
    int n = _read(0, into.ptr, into.len > 0x40000000 ? 0x40000000 : (unsigned)into.len);
#else
    ssize_t n = read(0, into.ptr, into.len);
#endif
    return n > 0 ? (uint64_t)n : 0;
}

// ---- fs: each native returns a status, >= 0 for a result and < 0 for an error, as in ctxi

enum { NOT_FOUND = -1, PERMISSION = -2, IS_DIR = -3, EXISTS = -4, NOT_DIR = -5, BAD_FILE = -6 };

static int64_t os_error(int e) {
    switch (e) {
    case ENOENT: return NOT_FOUND;
    case EACCES: case EPERM: return PERMISSION;
    case EISDIR: return IS_DIR;
    case EEXIST: return EXISTS;
    case ENOTDIR: return NOT_DIR;
    default: return -1000 - e;
    }
}

#define MAX_FILES 1024
static int files[MAX_FILES];            // id -> fd + 1; 0 is a free id
static uint32_t next_file = 1;

#ifdef _WIN32
typedef wchar_t path_char;
static path_char *os_path(ctx_slice p) {
    int n = MultiByteToWideChar(CP_UTF8, 0, p.ptr, (int)p.len, NULL, 0);
    wchar_t *w = malloc((n + 1) * sizeof *w);
    MultiByteToWideChar(CP_UTF8, 0, p.ptr, (int)p.len, w, n);
    w[n] = 0;
    return w;
}
#define OS_STAT _wstat64
typedef struct _stat64 os_stat_t;
#define OS_OPEN _wopen
#define OS_REMOVE _wremove
#else
typedef char path_char;
static path_char *os_path(ctx_slice p) { return c_string(p); }
#define OS_STAT stat
typedef struct stat os_stat_t;
#define OS_OPEN open
#define OS_REMOVE remove
#endif

// The path, or null with *status set if it is empty or a directory.
static path_char *checked_path(ctx_slice p, int64_t *status) {
    if (p.len == 0) { *status = NOT_FOUND; return NULL; }
    path_char *w = os_path(p);
    os_stat_t st;
    if (OS_STAT(w, &st) == 0 && (st.st_mode & S_IFMT) == S_IFDIR) {
        free(w);
        *status = IS_DIR;
        return NULL;
    }
    return w;
}

int64_t ctx_fs_sys_open(ctx_slice path, uint8_t mode) {
    static const int flags[] = {
        O_RDONLY, O_WRONLY | O_CREAT | O_TRUNC, O_WRONLY | O_CREAT | O_APPEND, O_WRONLY | O_CREAT | O_EXCL,
    };
    if (mode > 3) {
        char msg[64];
        snprintf(msg, sizeof msg, "invalid open mode %u", (unsigned)mode);
        ctx_panic_nopos(msg);
    }
    int64_t status = 0;
    path_char *w = checked_path(path, &status);
    if (!w) return status;
    int fd = OS_OPEN(w, flags[mode] | O_BINARY, 0666);
    int e = errno;
    free(w);
    if (fd < 0) return os_error(e);
    if (next_file >= MAX_FILES) ctx_panic_nopos("too many open files");
    uint32_t id = next_file++;
    files[id] = fd + 1;
    return id;
}

static int fd_of(uint32_t id) {
    return id < MAX_FILES ? files[id] - 1 : -1;
}

int64_t ctx_fs_sys_read(uint32_t file, ctx_slice into) {
    int fd = fd_of(file);
    if (fd < 0) return BAD_FILE;
    if (into.len == 0) return 0;
#ifdef _WIN32
    int n = _read(fd, into.ptr, into.len > 0x40000000 ? 0x40000000 : (unsigned)into.len);
#else
    ssize_t n = read(fd, into.ptr, into.len);
#endif
    return n < 0 ? os_error(errno) : n;
}

int64_t ctx_fs_sys_write(uint32_t file, ctx_slice bytes) {
    int fd = fd_of(file);
    if (fd < 0) return BAD_FILE;
    if (bytes.len == 0) return 0;
#ifdef _WIN32
    int n = _write(fd, bytes.ptr, bytes.len > 0x40000000 ? 0x40000000 : (unsigned)bytes.len);
#else
    ssize_t n = write(fd, bytes.ptr, bytes.len);
#endif
    return n < 0 ? os_error(errno) : n;
}

int64_t ctx_fs_sys_close(uint32_t file) {
    int fd = fd_of(file);
    if (fd < 0) return BAD_FILE;
    files[file] = 0;
    return close(fd) < 0 ? os_error(errno) : 0;
}

int64_t ctx_fs_sys_size(ctx_slice path) {
    int64_t status = 0;
    path_char *w = checked_path(path, &status);
    if (!w) return status;
    os_stat_t st;
    int r = OS_STAT(w, &st);
    int e = errno;
    free(w);
    return r < 0 ? os_error(e) : (int64_t)st.st_size;
}

int64_t ctx_fs_sys_remove(ctx_slice path) {
    int64_t status = 0;
    path_char *w = checked_path(path, &status);
    if (!w) return status;
    int r = OS_REMOVE(w);
    int e = errno;
    free(w);
    return r < 0 ? os_error(e) : 0;
}

// ---- mem

#define PAGE 4096
#define MAX_MEMORY (1ULL << 32)          // as ctxi: everything, stack included, within 4 GiB
static uint64_t used_memory = 64 + (16 << 20);

ctx_slice ctx_mem_sys_pages(uint64_t size) {
    ctx_slice out = { NULL, 0 };
    size = (size + PAGE - 1) / PAGE * PAGE;
    if (size == 0 || used_memory + size > MAX_MEMORY) return out;
#ifdef _WIN32
    void *p = VirtualAlloc(NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
#else
    void *p = aligned_alloc(PAGE, size);
    if (p) memset(p, 0, size);
#endif
    if (!p) return out;
    used_memory += size;
    out.ptr = p;
    out.len = size;
    return out;
}

// ---- startup and exit

static int arg_count;
static char **arg_values;

#ifdef __linux__
// Linux has no link flag for the main thread's stack: its size is RLIMIT_STACK, usually 8 MiB,
// below the 16 MiB check, so deep recursion would crash instead of panicking. The limit is
// raised to what Windows and macOS executables reserve, and the program runs itself again, since
// the kernel places the stack's neighbours when it starts a program. Once the limit is high
// enough, or can't be raised, this does nothing.
#define STACK_RESERVE (256ull << 20)
static void reserve_stack(char **argv) {
    struct rlimit rl;
    if (getrlimit(RLIMIT_STACK, &rl) != 0 || rl.rlim_cur == RLIM_INFINITY || rl.rlim_cur >= STACK_RESERVE)
        return;
    rlim_t want = STACK_RESERVE;
    if (rl.rlim_max != RLIM_INFINITY && want > rl.rlim_max) want = rl.rlim_max;
    if (want <= rl.rlim_cur) return;
    rl.rlim_cur = want;
    if (setrlimit(RLIMIT_STACK, &rl) != 0) return;
    execv("/proc/self/exe", argv);          // returns only if it failed; carry on as we are
}
#endif

void ctx_init(const char *const *table, uint32_t n, const char *program, int argc, char **argv) {
#ifdef __linux__
    reserve_stack(argv);
#endif
    program_name = program;
    arg_count = argc;
    arg_values = argv;
    ctx_files = table;
    ctx_nfiles = n;
    // The stack is ctxi's size, 16 MiB, or CTX_STACK bytes. The executable reserves far more
    // (tools/toolchain.py), so a frame that crosses the limit still has room to reach the check.
    char here;
    uint64_t size = 16 << 20;
    const char *env = getenv("CTX_STACK");
    if (env && *env) size = strtoull(env, NULL, 10);
    if (size > (200ull << 20)) size = 200ull << 20;
    ctx_stack_limit = &here - size;
#ifdef _WIN32
    _setmode(0, _O_BINARY);
    _setmode(1, _O_BINARY);
    _setmode(2, _O_BINARY);
#endif
}

ctx_slice ctx_args(void) {
    ctx_slice out = { NULL, 0 };
#ifdef _WIN32
    int argc = 0;
    wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (!argv || argc <= 1) return out;
    ctx_slice *items = ctx_alloc((argc - 1) * sizeof *items);
    for (int i = 1; i < argc; i++) {
        int n = WideCharToMultiByte(CP_UTF8, 0, argv[i], -1, NULL, 0, NULL, NULL) - 1;
        char *bytes = ctx_alloc(n + 1);
        WideCharToMultiByte(CP_UTF8, 0, argv[i], -1, bytes, n + 1, NULL, NULL);
        items[i - 1] = (ctx_slice){ n ? bytes : NULL, (uint64_t)n };
    }
    LocalFree(argv);
    out = (ctx_slice){ items, (uint64_t)(argc - 1) };
#else
    if (arg_count <= 1) return out;
    ctx_slice *items = ctx_alloc((arg_count - 1) * sizeof *items);
    for (int i = 1; i < arg_count; i++) {
        size_t n = strlen(arg_values[i]);
        items[i - 1] = (ctx_slice){ n ? arg_values[i] : NULL, (uint64_t)n };
    }
    out = (ctx_slice){ items, (uint64_t)(arg_count - 1) };
#endif
    return out;
}

// ---- build: a build program's graph (std/build.ctx), one record per line, its fields separated
// by tabs, to the file CTX_BUILD_OUT names, or to standard output without it:
//   exe ID NAME ROOT    link ID LIB    framework ID NAME    libpath ID PATH

static FILE *build_out;
static uint32_t build_exes;

static void build_field(ctx_slice s, const char *what) {
    const char *p = s.ptr;
    if (s.len == 0) {
        char msg[96];
        snprintf(msg, sizeof msg, "build: empty %s", what);
        ctx_panic_nopos(msg);
    }
    for (uint64_t i = 0; i < s.len; i++) {
        if (p[i] == '\t' || p[i] == '\n' || p[i] == '\r' || p[i] == 0) {
            char msg[96];
            snprintf(msg, sizeof msg, "build: a %s cannot hold a tab, a line break or a zero byte", what);
            ctx_panic_nopos(msg);
        }
    }
}

static void build_record(const char *kind, uint32_t id, ctx_slice a, ctx_slice b) {
    char head[64];
    int n = snprintf(head, sizeof head, "%s\t%u\t", kind, (unsigned)id);
    if (!build_out) {
        const char *path = getenv("CTX_BUILD_OUT");
        if (path && *path) {
            build_out = fopen(path, "wb");
            if (!build_out) ctx_panic_nopos("build: cannot write CTX_BUILD_OUT");
        }
    }
    if (build_out) {
        fwrite(head, 1, (size_t)n, build_out);
        fwrite(a.ptr, 1, a.len, build_out);
        if (b.len) { fputc('\t', build_out); fwrite(b.ptr, 1, b.len, build_out); }
        fputc('\n', build_out);
        fflush(build_out);
    } else {
        put_out(head, (size_t)n);
        put_out(a.ptr, a.len);
        if (b.len) { put_out("\t", 1); put_out(b.ptr, b.len); }
        put_out("\n", 1);
    }
}

static void build_check(uint32_t exe) {
    if (exe >= build_exes) {
        char msg[64];
        snprintf(msg, sizeof msg, "build: no executable %u", (unsigned)exe);
        ctx_panic_nopos(msg);
    }
}

ctx_build_exe ctx_build_exe_new(ctx_slice name, ctx_slice root) {
    build_field(name, "name");
    build_field(root, "root");
    ctx_build_exe exe = { build_exes++ };
    build_record("exe", exe.id, name, root);
    return exe;
}

void ctx_build_link(ctx_build_exe exe, ctx_slice lib) {
    build_check(exe.id);
    build_field(lib, "library");
    build_record("link", exe.id, lib, (ctx_slice){ NULL, 0 });
}

void ctx_build_framework(ctx_build_exe exe, ctx_slice name) {
    build_check(exe.id);
    build_field(name, "framework");
    build_record("framework", exe.id, name, (ctx_slice){ NULL, 0 });
}

void ctx_build_lib_path(ctx_build_exe exe, ctx_slice path) {
    build_check(exe.id);
    build_field(path, "library path");
    build_record("libpath", exe.id, path, (ctx_slice){ NULL, 0 });
}

uint32_t ctx_build_os(void) {
#if defined(_WIN32)
    return 0;
#elif defined(__APPLE__)
    return 1;
#else
    return 2;
#endif
}

int ctx_exit(int32_t code) {
    flush_out();
    if (build_out) fclose(build_out);
    for (uint32_t i = 1; i < next_file; i++)
        if (files[i]) close(files[i] - 1);
    return code;
}
