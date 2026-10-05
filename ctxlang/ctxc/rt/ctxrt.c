// ctxrt: see ctxrt.h. It calls no C library function: panics write their messages themselves
// and leave reporting them to the program's `#panic` fn, starting the program is its `#start`
// fn's, and function values' records take pages from a fn that std's start gives (std/rt.ctx).

#include "ctxrt.h"

static const char *program_name = "program";
static const char *const *ctx_files;
static uint32_t ctx_nfiles;
static ctx_panic_fn panic_fn;
char *ctx_stack_limit;

void ctx_start(const char *const *files, uint32_t nfiles, const char *program, ctx_panic_fn on_panic) {
    ctx_files = files;
    ctx_nfiles = nfiles;
    program_name = program;
    panic_fn = on_panic;
}

void ctx_stack_set(uint64_t limit) {
    ctx_stack_limit = (char *)(uintptr_t)limit;
}

// ---- std's state: zeroed, in the program's image, so it costs nothing until it is touched

#define CTX_STATE_SIZE (1u << 17)
static _Alignas(64) unsigned char state[CTX_STATE_SIZE];

void *ctx_state(uint64_t size) {
    if (size > sizeof state) __builtin_trap();
    return state;
}

// ---- panics

static uint64_t c_len(const char *s) {
    uint64_t n = 0;
    while (s[n]) n++;
    return n;
}

// How a position names its file (ctxc/emit_c.ctx): FNV-1a of the name, with the top bit set, so
// that a file's id doesn't depend on which other files the program has. An id below the table's
// length is an index into it, as C from an older ctxc has it.
static uint32_t file_id(const char *name) {
    uint32_t h = 2166136261u;
    for (; *name; name++) h = (h ^ (uint8_t)*name) * 16777619u;
    return h | 0x80000000u;
}

static const char *file_name(uint32_t file) {
    const char *name = NULL;
    if (file < ctx_nfiles) {
        name = ctx_files[file];
    } else {
        for (uint32_t i = 0; i < ctx_nfiles && !name; i++)
            if (file_id(ctx_files[i]) == file) name = ctx_files[i];
    }
    if (name && name[0]) return name;
    return program_name;
}

// Calls the panic fn once. The stack check is off while it runs: a stack overflow has used the
// stack up to the limit, and the executable reserves more than that beyond it.
_Noreturn static void report(const char *where, uint32_t line, uint32_t col, const char *msg, uint64_t len) {
    static int panicking;
    if (!panicking && panic_fn) {
        panicking = 1;
        ctx_stack_limit = NULL;
        panic_fn((ctx_slice){ (void *)msg, len }, (ctx_slice){ (void *)where, c_len(where) }, line, col);
    }
    __builtin_trap();
}

_Noreturn void ctx_panic(uint32_t line, uint32_t col, uint32_t file, const char *msg) {
    report(file_name(file), line, col, msg, c_len(msg));
}

_Noreturn void ctx_panic_nopos(const char *msg) {
    report(program_name, 0, 0, msg, c_len(msg));
}

_Noreturn void ctx_panic_msg(ctx_slice msg) {
    report(program_name, 0, 0, msg.ptr ? msg.ptr : "", msg.len);
}

// A message of pieces: text, and numbers in decimal.
typedef struct { char text[192]; uint64_t len; } message;

static void text(message *m, const char *s) {
    for (; *s && m->len < sizeof m->text - 1; s++) m->text[m->len++] = *s;
    m->text[m->len] = 0;
}

static void unsigned_number(message *m, uint64_t n) {
    char digits[20];
    int k = 0;
    do { digits[k++] = (char)('0' + n % 10); n /= 10; } while (n);
    while (k > 0 && m->len < sizeof m->text - 1) m->text[m->len++] = digits[--k];
    m->text[m->len] = 0;
}

static void signed_number(message *m, int64_t n) {
    if (n < 0) {
        text(m, "-");
        unsigned_number(m, 0 - (uint64_t)n);
    } else {
        unsigned_number(m, (uint64_t)n);
    }
}

_Noreturn void ctx_panic_index(uint64_t i, uint64_t n, CTX_POS) {
    message m = { "", 0 };
    text(&m, "index ");
    unsigned_number(&m, i);
    text(&m, " out of bounds for length ");
    unsigned_number(&m, n);
    ctx_panic(line, col, file, m.text);
}

_Noreturn void ctx_panic_range(uint64_t lo, uint64_t hi, uint64_t n, CTX_POS) {
    message m = { "", 0 };
    text(&m, "range ");
    unsigned_number(&m, lo);
    text(&m, "..");
    unsigned_number(&m, hi);
    text(&m, " out of bounds for length ");
    unsigned_number(&m, n);
    ctx_panic(line, col, file, m.text);
}

_Noreturn void ctx_panic_shift_s(int64_t n, int bits, CTX_POS) {
    message m = { "", 0 };
    text(&m, "shift count ");
    signed_number(&m, n);
    text(&m, " out of range for a ");
    signed_number(&m, bits);
    text(&m, "-bit integer");
    ctx_panic(line, col, file, m.text);
}

_Noreturn void ctx_panic_shift_u(uint64_t n, int bits, CTX_POS) {
    message m = { "", 0 };
    text(&m, "shift count ");
    unsigned_number(&m, n);
    text(&m, " out of range for a ");
    signed_number(&m, bits);
    text(&m, "-bit integer");
    ctx_panic(line, col, file, m.text);
}

_Noreturn void ctx_panic_as_s(int64_t v, const char *dst, CTX_POS) {
    message m = { "", 0 };
    text(&m, "@as: ");
    signed_number(&m, v);
    text(&m, " is not representable in ");
    text(&m, dst);
    ctx_panic(line, col, file, m.text);
}

_Noreturn void ctx_panic_as_u(uint64_t v, const char *dst, CTX_POS) {
    message m = { "", 0 };
    text(&m, "@as: ");
    unsigned_number(&m, v);
    text(&m, " is not representable in ");
    text(&m, dst);
    ctx_panic(line, col, file, m.text);
}

// ---- function values' records
//
// Memory comes from the pages fn std's start gives (ctx_pages_set), and before it from the
// image: zeroed, so it costs nothing until it is touched.

static ctx_pages_fn pages_fn;
static int growing;

void ctx_pages_set(ctx_pages_fn pages) {
    pages_fn = pages;
}

// n bytes of pages, n a multiple of PAGE, or a panic.
#define PAGE ((uint64_t)4096)
#define PAGES(n) (((n) + PAGE - 1) / PAGE * PAGE)

static char *pages(uint64_t n) {
    if (growing) __builtin_trap();          // the pages fn made a record that needed more
    char *p = NULL;
    if (pages_fn) {
        growing = 1;
        p = pages_fn(n);
        growing = 0;
    }
    if (!p) {
        pages_fn = NULL;
        ctx_panic_nopos("out of memory for function values");
    }
    return p;
}

// Borrowed records: a stack of segments. A function that may make one saves the top on entry
// and restores it on return (CTX_RECORDS), so a record lives until its invocation returns, and
// the next call reuses its memory. A segment never moves or goes back to the system.

static _Alignas(16) char first_space[1 << 16];
static ctx_rec_seg first_seg = { NULL, first_space, first_space + sizeof first_space };
ctx_rec_mark ctx_recs = { &first_seg, first_space, first_space + sizeof first_space };

#define SEGMENT ((uint64_t)1 << 18)

void *ctx_rec_more(uint64_t n) {
    ctx_rec_seg *s = ctx_recs.seg->next;
    while (s && (uint64_t)(s->end - s->data) < n) s = s->next;
    if (!s) {
        uint64_t size = n + 32 > SEGMENT ? PAGES(n + 32) : SEGMENT;
        char *p = pages(size);
        s = (ctx_rec_seg *)p;
        s->data = p + 32;
        s->end = p + size;
        s->next = ctx_recs.seg->next;
        ctx_recs.seg->next = s;
    }
    ctx_recs.seg = s;
    ctx_recs.top = s->data + n;
    ctx_recs.end = s->end;
    return s->data;
}

// Permanent records: bump allocation, never freed.
void *ctx_alloc(size_t n) {
    static _Alignas(16) char space[1 << 14];
    static char *at = space, *end = space + sizeof space;
    n = (n + 15) & ~(size_t)15;
    if ((size_t)(end - at) < n) {
        uint64_t size = n > (1 << 16) ? PAGES(n) : (1 << 16);
        at = pages(size);
        end = at + size;
    }
    void *p = at;
    at += n;
    return p;
}

// Adapters of `fn` values, one for each inner value and code. Such a value is a named
// function's static record or another of these, so there are finitely many.
typedef struct ctx_canon { struct ctx_canon *next; ctx_adapter a; } ctx_canon;

ctx_fn *ctx_adapt(ctx_fn *inner, void (*code)(void)) {
    static ctx_canon *table[256];
    uintptr_t h = (uintptr_t)inner * 31 + (uintptr_t)code;
    h ^= h >> 17;
    ctx_canon **b = &table[(h ^ (h >> 8)) & 255];
    for (ctx_canon *c = *b; c; c = c->next)
        if (c->a.inner == inner && c->a.base.code == code) return &c->a.base;
    ctx_canon *c = ctx_alloc(sizeof *c);
    c->a.base.code = code;
    c->a.inner = inner;
    c->next = *b;
    *b = c;
    return &c->a.base;
}
