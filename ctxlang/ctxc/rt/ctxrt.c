// ctxrt: see ctxrt.h. Of the C library it uses calloc and free alone, for function values'
// records: panics write their messages themselves and leave reporting them to the program's
// `#panic` fn, and starting the program is its `#start` fn's (std/rt.ctx).

#include "ctxrt.h"

#include <stdlib.h>

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

// ---- escaping callable records: permanent bump allocation

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

// Borrowed records live until their creating invocation exits, including nested calls.
// A long-running invocation retains every record until exit, rather than reusing a site.
struct ctx_bind_node {
    struct ctx_bind_node *next;
    max_align_t alignment;
    unsigned char data[];
};

void *ctx_borrow_alloc(ctx_bind_scope *scope, size_t n) {
    ctx_bind_node *node = calloc(1, sizeof *node + n);
    if (!node) ctx_panic_nopos("out of memory");
    node->next = scope->head;
    scope->head = node;
    return node->data;
}

void ctx_bind_release(ctx_bind_scope *scope) {
    ctx_bind_node *node = scope->head;
    while (node) {
        ctx_bind_node *next = node->next;
        free(node);
        node = next;
    }
    scope->head = NULL;
}
