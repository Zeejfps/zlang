// ctxrt: see ctxrt.h. Written against mingw-w64 (Windows) and POSIX.

#define __USE_MINGW_ANSI_STDIO 1     // C99 printf: two-digit exponents, %llu
#include "ctxrt.h"

#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>

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
#endif

static const char *program_name = "program";
static const char *const *ctx_files;
static uint32_t ctx_nfiles;
char *ctx_stack_limit;

// ---- output: standard output is buffered and flushed before anything else is written or read.
// std's io fills the buffer (std/io.ctx, `Out`); a panic and ctx_exit flush it here.

static char out_buf[1 << 16];
static struct { ctx_slice buf; uint64_t len; } stdout_buf = { { out_buf, sizeof out_buf }, 0 };

void *ctx_io_out(void) {
    return &stdout_buf;
}

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
    write_all(1, out_buf, stdout_buf.len);
    stdout_buf.len = 0;
}

static void put_out(const void *p, size_t n) {
    if (stdout_buf.len + n > sizeof out_buf) flush_out();
    if (n > sizeof out_buf) { write_all(1, p, n); return; }
    memcpy(out_buf + stdout_buf.len, p, n);
    stdout_buf.len += n;
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

// ---- statuses: >= 0 for a result and < 0 for an error, for proc's natives

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

// ---- proc: other programs, and this one's environment

// Runs argv[0], found on PATH unless it holds a path separator, with this program's
// environment plus the "KEY=VALUE" entries of `env` (an entry replaces one of the same key),
// sharing standard input, output and error, and waits for it. Returns 0 and sets *code to its
// exit code, 128 + N if signal N killed it, or returns a status < 0 if it couldn't start.
#ifdef _WIN32
// Appends arg to the command line as CommandLineToArgvW reads it back: quoted if it is empty or
// holds a space, a tab or a quote, with backslashes doubled before a quote.
static void quote_arg(char **line, size_t *len, size_t *cap, ctx_slice arg) {
    const char *a = arg.ptr;
    size_t need = *len + 2 * arg.len + 4;
    if (need > *cap) {
        *cap = need * 2;
        *line = realloc(*line, *cap);
        if (!*line) ctx_panic_nopos("out of memory");
    }
    char *o = *line + *len;
    if (*len > 0) *o++ = ' ';
    int plain = arg.len > 0;
    for (uint64_t i = 0; i < arg.len; i++)
        if (a[i] == ' ' || a[i] == '\t' || a[i] == '"' || a[i] == '\n' || a[i] == '\v') plain = 0;
    if (plain) {
        memcpy(o, a, arg.len);
        o += arg.len;
    } else {
        *o++ = '"';
        size_t slashes = 0;
        for (uint64_t i = 0; i < arg.len; i++) {
            if (a[i] == '\\') { slashes++; continue; }
            if (a[i] == '"') { for (size_t k = 0; k < slashes * 2 + 1; k++) *o++ = '\\'; }
            else { for (size_t k = 0; k < slashes; k++) *o++ = '\\'; }
            slashes = 0;
            *o++ = a[i];
        }
        for (size_t k = 0; k < slashes * 2; k++) *o++ = '\\';
        *o++ = '"';
    }
    *len = (size_t)(o - *line);
}

static wchar_t *widen(const char *p, size_t n) {
    int w = MultiByteToWideChar(CP_UTF8, 0, p, (int)n, NULL, 0);
    wchar_t *out = malloc((w + 1) * sizeof *out);
    if (!out) ctx_panic_nopos("out of memory");
    MultiByteToWideChar(CP_UTF8, 0, p, (int)n, out, w);
    out[w] = 0;
    return out;
}
#else
#include <spawn.h>
#include <sys/wait.h>
extern char **environ;
#endif

// Whether environment entry `entry` ("KEY=VALUE") has the key of one of `env`'s entries.
static int overridden(const char *entry, ctx_slice env) {
    const char *eq = strchr(entry + (entry[0] == '='), '=');      // Windows has "=C:=C:\..."
    size_t key = eq ? (size_t)(eq - entry) : strlen(entry);
    ctx_slice *items = env.ptr;
    for (uint64_t i = 0; i < env.len; i++) {
        const char *e = items[i].ptr;
        if (items[i].len > key && e[key] == '=' &&
#ifdef _WIN32
            _strnicmp(e, entry, key) == 0
#else
            memcmp(e, entry, key) == 0
#endif
        ) return 1;
    }
    return 0;
}

int64_t ctx_proc_run(ctx_slice argv, ctx_slice env, int32_t *code) {
    ctx_slice *args = argv.ptr;
    ctx_slice *extra = env.ptr;
    if (argv.len == 0) ctx_panic_nopos("proc: run needs a program to run");
    for (uint64_t i = 0; i < env.len; i++) {
        const char *e = extra[i].ptr;
        if (extra[i].len == 0 || !memchr(e, '=', extra[i].len) || e[0] == '=')
            ctx_panic_nopos("proc: an environment entry is KEY=VALUE");
    }
    flush_out();
#ifdef _WIN32
    char *line = NULL;
    size_t len = 0, cap = 0;
    for (uint64_t i = 0; i < argv.len; i++) quote_arg(&line, &len, &cap, args[i]);
    wchar_t *wline = widen(line ? line : "", len);
    free(line);
    // The environment block: "KEY=VALUE\0" entries, then another \0.
    wchar_t *inherited = GetEnvironmentStringsW();
    size_t wlen = 0, wcap = 1024;
    wchar_t *block = malloc(wcap * sizeof *block);
    if (!block) ctx_panic_nopos("out of memory");
    for (wchar_t *e = inherited; *e; e += wcslen(e) + 1) {
        int n = WideCharToMultiByte(CP_UTF8, 0, e, -1, NULL, 0, NULL, NULL);
        char *u = malloc(n);
        if (!u) ctx_panic_nopos("out of memory");
        WideCharToMultiByte(CP_UTF8, 0, e, -1, u, n, NULL, NULL);
        int skip = overridden(u, env);
        free(u);
        if (skip) continue;
        size_t n16 = wcslen(e) + 1;
        if (wlen + n16 + 1 > wcap) {
            wcap = (wlen + n16 + 1) * 2;
            block = realloc(block, wcap * sizeof *block);
            if (!block) ctx_panic_nopos("out of memory");
        }
        memcpy(block + wlen, e, n16 * sizeof *block);
        wlen += n16;
    }
    FreeEnvironmentStringsW(inherited);
    for (uint64_t i = 0; i < env.len; i++) {
        wchar_t *w = widen(extra[i].ptr, extra[i].len);
        size_t n16 = wcslen(w) + 1;
        if (wlen + n16 + 1 > wcap) {
            wcap = (wlen + n16 + 1) * 2;
            block = realloc(block, wcap * sizeof *block);
            if (!block) ctx_panic_nopos("out of memory");
        }
        memcpy(block + wlen, w, n16 * sizeof *block);
        wlen += n16;
        free(w);
    }
    block[wlen] = 0;
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    memset(&si, 0, sizeof si);
    si.cb = sizeof si;
    BOOL ok = CreateProcessW(NULL, wline, NULL, NULL, TRUE, CREATE_UNICODE_ENVIRONMENT, block, NULL, &si, &pi);
    DWORD e = GetLastError();
    free(wline);
    free(block);
    if (!ok) {
        if (e == ERROR_FILE_NOT_FOUND || e == ERROR_PATH_NOT_FOUND) return NOT_FOUND;
        if (e == ERROR_ACCESS_DENIED) return PERMISSION;
        return -1000 - (int64_t)e;
    }
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD exit_code = 0;
    GetExitCodeProcess(pi.hProcess, &exit_code);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    *code = (int32_t)exit_code;
    return 0;
#else
    char **cargv = malloc((argv.len + 1) * sizeof *cargv);
    if (!cargv) ctx_panic_nopos("out of memory");
    for (uint64_t i = 0; i < argv.len; i++) cargv[i] = c_string(args[i]);
    cargv[argv.len] = NULL;
    size_t n = 0;
    while (environ[n]) n++;
    char **cenv = malloc((n + env.len + 1) * sizeof *cenv);
    if (!cenv) ctx_panic_nopos("out of memory");
    size_t k = 0;
    for (size_t i = 0; i < n; i++)
        if (!overridden(environ[i], env)) cenv[k++] = environ[i];
    for (uint64_t i = 0; i < env.len; i++) cenv[k++] = c_string(extra[i]);
    cenv[k] = NULL;
    pid_t pid;
    int r = posix_spawnp(&pid, cargv[0], NULL, NULL, cargv, cenv);
    for (uint64_t i = 0; i < argv.len; i++) free(cargv[i]);
    free(cargv);
    for (size_t i = k - env.len; i < k; i++) free(cenv[i]);
    free(cenv);
    if (r != 0) return os_error(r);
    int status;
    while (waitpid(pid, &status, 0) < 0)
        if (errno != EINTR) return os_error(errno);
    if (WIFEXITED(status)) *code = WEXITSTATUS(status);
    else if (WIFSIGNALED(status)) *code = 128 + WTERMSIG(status);
    else *code = 255;
    return 0;
#endif
}

// Environment variable `name` into *value, which lives until the program ends. 0 if it isn't set.
// Windows' only: elsewhere std reads C's environ itself (std/os/posix).
#ifdef _WIN32
bool ctx_proc_env(ctx_slice name, ctx_slice *value) {
    wchar_t *w = widen(name.ptr ? name.ptr : "", name.len);
    const wchar_t *v = _wgetenv(w);
    free(w);
    if (!v) return 0;
    int n = WideCharToMultiByte(CP_UTF8, 0, v, -1, NULL, 0, NULL, NULL);
    char *u = ctx_alloc(n);
    WideCharToMultiByte(CP_UTF8, 0, v, -1, u, n, NULL, NULL);
    *value = (ctx_slice){ u, (uint64_t)(n - 1) };
    return 1;
}
#endif

// The absolute path of this program's executable; empty if the OS won't say.
#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif
ctx_slice ctx_proc_exe_path(void) {
    static char *path;
    if (!path) {
#if defined(_WIN32)
        wchar_t w[32768];
        DWORD n = GetModuleFileNameW(NULL, w, 32768);
        if (n == 0 || n >= 32768) return (ctx_slice){ NULL, 0 };
        int u = WideCharToMultiByte(CP_UTF8, 0, w, (int)n, NULL, 0, NULL, NULL);
        path = ctx_alloc(u + 1);
        WideCharToMultiByte(CP_UTF8, 0, w, (int)n, path, u, NULL, NULL);
        for (int i = 0; i < u; i++) if (path[i] == '\\') path[i] = '/';
#elif defined(__APPLE__)
        char buf[4096];
        uint32_t size = sizeof buf;
        if (_NSGetExecutablePath(buf, &size) != 0) return (ctx_slice){ NULL, 0 };
        char *real = realpath(buf, NULL);
        if (!real) return (ctx_slice){ NULL, 0 };
        path = real;
#else
        char buf[4096];
        ssize_t n = readlink("/proc/self/exe", buf, sizeof buf - 1);
        if (n <= 0) return (ctx_slice){ NULL, 0 };
        buf[n] = 0;
        path = ctx_alloc((size_t)n + 1);
        memcpy(path, buf, (size_t)n + 1);
#endif
    }
    return (ctx_slice){ path, strlen(path) };
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
    return code;
}
