// ctxrt: see ctxrt.h. It calls no C library function: panics write their messages themselves
// and leave reporting them to the program's `#panic` fn, starting the program is its `#start`
// fn's, and function values' records take pages from a fn that std's start gives (std/rt.ctx).
//
// It is compiled once for every program, threaded or not (ctxrt.h, CTX_THREADS). In a threaded
// program ctxthread.c's setup gives it the calling thread's state (ctx_current) and turns on
// its lock, a spin lock around what threads share: the pages for records and the permanent
// records. In any other, the main thread's state is the only one, and nothing is locked.

#include "ctxrt.h"

// ---- threads

static ctx_thread *main_thread(void) { return &ctx_main_thread; }

// The calling thread's state, and whether the program is threaded: ctxthread.c's setup sets
// both. For the paths that aren't hot: a function reads CTX_HERE.
ctx_thread *(*ctx_current)(void) = main_thread;
int ctx_threaded;

// The calling thread's frame that last called C (ctxrt.h, call paths), which ctxthread.c's
// setup reads and writes as the thread's own.
static ctx_frame *main_frames(void) { return ctx_main_thread.frames; }
static void main_frames_put(ctx_frame *f) { ctx_main_thread.frames = f; }
ctx_frame *(*ctx_frames_now)(void) = main_frames;
void (*ctx_frames_put)(ctx_frame *f) = main_frames_put;

const ctx_where ctx_c_code = { "C code", 0, CTX_C_CODE };

static int lock_word;

static void spin_pause(void) {
#if defined(__x86_64__)
    __builtin_ia32_pause();
#elif defined(__aarch64__)
    __asm__ volatile("yield");
#endif
}

static void lock(void) {
    if (!ctx_threaded) return;
    while (__atomic_exchange_n(&lock_word, 1, __ATOMIC_ACQUIRE)) {
        while (__atomic_load_n(&lock_word, __ATOMIC_RELAXED)) spin_pause();
    }
}

static void unlock(void) {
    if (ctx_threaded) __atomic_store_n(&lock_word, 0, __ATOMIC_RELEASE);
}

ctx_slice ctx_here_name(void) {
    ctx_thread *t = ctx_current();
    return (ctx_slice){ t->name, t->name_len };
}

ctx_end_fn ctx_thread_ends;

void ctx_ends_set(ctx_end_fn ends) {
    ctx_thread_ends = ends;
}

static const char *program_name = "program";
static const char *const *ctx_files;
static uint32_t ctx_nfiles;
static ctx_panic_fn panic_fn;

void ctx_start(const char *const *files, uint32_t nfiles, const char *program, ctx_panic_fn on_panic) {
    ctx_files = files;
    ctx_nfiles = nfiles;
    program_name = program;
    panic_fn = on_panic;
}

// ---- panics

static uint64_t c_len(const char *s) {
    uint64_t n = 0;
    while (s[n]) n++;
    return n;
}

// How a ctx_where names its file (ctxc/emit_c.ctx): FNV-1a of the name, with the top bit set, so
// that a file's id doesn't depend on which other files the program has; 0 is no file.
static uint32_t file_id(const char *name) {
    uint32_t h = 2166136261u;
    for (; *name; name++) h = (h ^ (uint8_t)*name) * 16777619u;
    return h | 0x80000000u;
}

// The file's name: the program's for a file named "" and for one the table doesn't have.
static const char *file_name(uint32_t file) {
    const char *name = NULL;
    for (uint32_t i = 0; file && i < ctx_nfiles && !name; i++)
        if (file_id(ctx_files[i]) == file) name = ctx_files[i];
    if (name && name[0]) return name;
    return program_name;
}

// Calls the panic fn once for the program. C's main's ctx_on_panic turns the calling thread's
// stack check off before it runs: a stack overflow has used the stack up to the limit, and the
// thread's stack reserves more than that beyond it. A panic on another thread meanwhile waits
// for the program to end; a panic while its own thread reports one traps.
// `in` is the function the panic is in, with its position, or null for a panic without one,
// and `up` the frame its path goes on from: the function's caller's, or for a panic without a
// position that of the function that called the native. The thread keeps them, for the panic
// fn to read the call path (ctx_path_frame).
_Noreturn static void report(const ctx_where *in, uint32_t line, uint32_t col, ctx_frame *up, const char *msg, uint64_t len) {
    static int panicking;
    ctx_thread *t = ctx_current();
    if (panic_fn && !t->reporting) {
        if (__atomic_exchange_n(&panicking, 1, __ATOMIC_ACQ_REL)) {
            for (;;) spin_pause();
        }
        t->panic_frames = up;
        t->panic_in = in;
        t->panic_line = line;
        t->panic_col = col;
        t->reporting = 1;
        const char *where = in ? file_name(in->file) : program_name;
        panic_fn((ctx_slice){ (void *)msg, len }, (ctx_slice){ (void *)where, c_len(where) }, line, col);
    }
    __builtin_trap();
}

_Noreturn void ctx_panic(uint32_t line, uint32_t col, const ctx_where *in, ctx_frame *up, const char *msg) {
    report(in, line, col, up, msg, c_len(msg));
}

_Noreturn void ctx_panic_nopos(const char *msg) {
    report(NULL, 0, 0, ctx_frames_now(), msg, c_len(msg));
}

_Noreturn void ctx_panic_msg(ctx_slice msg) {
    report(NULL, 0, 0, ctx_frames_now(), msg.ptr ? msg.ptr : "", msg.len);
}

_Noreturn void ctx_stack_overflow(ctx_frame *up) {
    report(NULL, 0, 0, up, "stack overflow", 14);
}

// ---- call paths (ctxrt.h)

// The runtime is where a function called it without noting its frame, as for a record: the
// frame the thread has noted may be of a call that has returned, so what the runtime calls or
// reports from here has no path.
static void unplaced(void) {
    ctx_frames_put(NULL);
}

// A path being read: the frames left, the panic's own position if it is still to give, and the
// task whose start ends it.
typedef struct { ctx_frame *f; const ctx_where *in; uint32_t line, col; ctx_task_rec *task; } path;

static void path_start(path *p) {
    ctx_thread *t = ctx_current();
    if (t->reporting) {
        p->f = t->panic_frames;
        p->in = t->panic_in;
        p->line = t->panic_line;
        p->col = t->panic_col;
    } else {
        p->f = ctx_frames_now();
        p->in = NULL;
        p->line = p->col = 0;
    }
    p->task = t->task;
}

static void entry_of(ctx_path_entry *e, const ctx_where *in, uint32_t line, uint32_t col, uint32_t kind) {
    const char *file = in->file ? file_name(in->file) : "";
    e->name = (ctx_slice){ (void *)in->name, c_len(in->name) };
    e->file = (ctx_slice){ (void *)file, c_len(file) };
    e->line = line;
    e->col = line ? col : 0;
    e->kind = kind;
    if (in->kind == CTX_C_CODE) {
        e->name.len = e->file.len = 0;
        e->line = e->col = 0;
        e->kind = 1;
    }
}

// The path's next entry into e: 0 at its end. The panic's own position comes first, then the
// frames from its function's caller's on. Functions the compiler wrote are left out, and the
// path ends at what calls main, a test or a task, and then says where the task was started.
static int path_next(path *p, ctx_path_entry *e) {
    if (p->in) {
        const ctx_where *in = p->in;
        p->in = NULL;
        if (in->kind == CTX_ENDS) p->f = NULL;
        entry_of(e, in, p->line, p->col, 0);
        return 1;
    }
    while (p->f) {
        ctx_frame *f = p->f;
        if (f->in->kind == CTX_ENDS) {
            p->f = NULL;
            break;
        }
        p->f = f->up;
        if (f->in->kind == CTX_HIDDEN) continue;
        entry_of(e, f->in, f->at & 0xFFFFF, f->at >> 20, 0);
        return 1;
    }
    if (p->task) {
        ctx_task_rec *r = p->task;
        p->task = NULL;
        if (r->in) {
            entry_of(e, r->in, r->line, r->col, 2);
            return 1;
        }
    }
    return 0;
}

uint64_t ctx_path_count(void) {
    path p;
    ctx_path_entry e;
    uint64_t n = 0;
    path_start(&p);
    while (path_next(&p, &e)) n++;
    return n;
}

ctx_path_entry ctx_path_frame(uint64_t index) {
    path p;
    ctx_path_entry e;
    path_start(&p);
    for (uint64_t i = 0; path_next(&p, &e); i++)
        if (i == index) return e;
    return (ctx_path_entry){ { (void *)"", 0 }, { (void *)"", 0 }, 0, 0, 0 };
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
    ctx_panic(line, col, in, up, m.text);
}

_Noreturn void ctx_panic_range(uint64_t lo, uint64_t hi, uint64_t n, CTX_POS) {
    message m = { "", 0 };
    text(&m, "range ");
    unsigned_number(&m, lo);
    text(&m, "..");
    unsigned_number(&m, hi);
    text(&m, " out of bounds for length ");
    unsigned_number(&m, n);
    ctx_panic(line, col, in, up, m.text);
}

_Noreturn void ctx_panic_index_s(int64_t i, uint64_t n, CTX_POS) {
    message m = { "", 0 };
    text(&m, "index ");
    signed_number(&m, i);
    text(&m, " out of bounds for length ");
    unsigned_number(&m, n);
    ctx_panic(line, col, in, up, m.text);
}

_Noreturn void ctx_panic_range_s(uint64_t lo, uint64_t hi, uint64_t n, int sg, CTX_POS) {
    message m = { "", 0 };
    text(&m, "range ");
    if (sg & 1) signed_number(&m, (int64_t)lo); else unsigned_number(&m, lo);
    text(&m, "..");
    if (sg & 2) signed_number(&m, (int64_t)hi); else unsigned_number(&m, hi);
    text(&m, " out of bounds for length ");
    unsigned_number(&m, n);
    ctx_panic(line, col, in, up, m.text);
}

_Noreturn void ctx_panic_shift_s(int64_t n, int bits, CTX_POS) {
    message m = { "", 0 };
    text(&m, "shift count ");
    signed_number(&m, n);
    text(&m, " out of range for a ");
    signed_number(&m, bits);
    text(&m, "-bit integer");
    ctx_panic(line, col, in, up, m.text);
}

_Noreturn void ctx_panic_shift_u(uint64_t n, int bits, CTX_POS) {
    message m = { "", 0 };
    text(&m, "shift count ");
    unsigned_number(&m, n);
    text(&m, " out of range for a ");
    signed_number(&m, bits);
    text(&m, "-bit integer");
    ctx_panic(line, col, in, up, m.text);
}

_Noreturn void ctx_panic_as_s(int64_t v, const char *dst, CTX_POS) {
    message m = { "", 0 };
    text(&m, "@as: ");
    signed_number(&m, v);
    text(&m, " is not representable in ");
    text(&m, dst);
    ctx_panic(line, col, in, up, m.text);
}

_Noreturn void ctx_panic_as_u(uint64_t v, const char *dst, CTX_POS) {
    message m = { "", 0 };
    text(&m, "@as: ");
    unsigned_number(&m, v);
    text(&m, " is not representable in ");
    text(&m, dst);
    ctx_panic(line, col, in, up, m.text);
}

// ---- function values' records
//
// Memory comes from the pages fn std's start gives (ctx_pages_set), and before it from the
// image: zeroed, so it costs nothing until it is touched.

static ctx_pages_fn pages_fn;

void ctx_pages_set(ctx_pages_fn pages) {
    pages_fn = pages;
}

// n bytes of pages, n a multiple of PAGE, or a panic. With the lock held: the panic unlocks it.
#define PAGE ((uint64_t)4096)
#define PAGES(n) (((n) + PAGE - 1) / PAGE * PAGE)

static char *pages(ctx_thread *t, uint64_t n) {
    if (t->growing) __builtin_trap();       // the pages fn made a record that needed more
    char *p = NULL;
    unplaced();                             // the pages fn is a callback, and running out a panic
    if (pages_fn) {
        t->growing = 1;
        p = pages_fn(n);
        t->growing = 0;
    }
    if (!p) {
        pages_fn = NULL;
        unlock();
        ctx_panic_nopos("out of memory for function values");
    }
    return p;
}

// Before taking the lock to take pages: the pages fn made a record that needed more, which
// would wait for the lock its own thread holds.
static void not_growing(ctx_thread *t) {
    if (ctx_threaded && t->growing) __builtin_trap();
}

// Borrowed records: a stack of segments for each thread. A function that may make one saves
// the top on entry and restores it on return (CTX_RECORDS), so a record lives until its
// invocation returns, and the next call reuses its memory. A segment never moves or goes back
// to the system: when a thread ends, its segments go to a pool that the next thread takes
// them from (ctx_rec_give).

static _Alignas(16) char first_space[1 << 16];
static ctx_rec_seg first_seg = { NULL, first_space, first_space + sizeof first_space, NULL };
ctx_thread ctx_main_thread = {
    0, { &first_seg, first_space, first_space + sizeof first_space }, &first_seg, 0, 0, 0, { 0 },
    NULL, NULL, NULL, 0, 0, NULL,
};

static ctx_rec_seg *pool;                    // ended threads' segments, by their first

#define SEGMENT ((uint64_t)1 << 18)

void *ctx_rec_more(ctx_thread *t, uint64_t n) {
    if (!t->head && pool) {
        lock();
        if (pool) {
            t->head = pool;
            pool = pool->pool;
        }
        unlock();
    }
    ctx_rec_seg *s = t->recs.seg ? t->recs.seg->next : t->head;
    while (s && (uint64_t)(s->end - s->data) < n) s = s->next;
    if (!s) {
        uint64_t size = n + 32 > SEGMENT ? PAGES(n + 32) : SEGMENT;
        not_growing(t);
        lock();
        char *p = pages(t, size);
        unlock();
        s = (ctx_rec_seg *)p;
        s->data = p + 32;
        s->end = p + size;
        s->pool = NULL;
        if (t->recs.seg) {
            s->next = t->recs.seg->next;
            t->recs.seg->next = s;
        } else {
            s->next = t->head;
            t->head = s;
        }
    }
    t->recs.seg = s;
    t->recs.top = s->data + n;
    t->recs.end = s->end;
    return s->data;
}

// A thread that ends gives its segments to the pool (ctxthread.c).
void ctx_rec_give(ctx_thread *t) {
    if (!t->head) return;
    lock();
    t->head->pool = pool;
    pool = t->head;
    unlock();
    t->head = NULL;
}

// Permanent records: bump allocation, never freed. With the lock held.
static void *alloc_locked(ctx_thread *t, size_t n) {
    static _Alignas(16) char space[1 << 14];
    static char *at = space, *end = space + sizeof space;
    n = (n + 15) & ~(size_t)15;
    if ((size_t)(end - at) < n) {
        uint64_t size = n > (1 << 16) ? PAGES(n) : (1 << 16);
        at = pages(t, size);
        end = at + size;
    }
    void *p = at;
    at += n;
    return p;
}

void *ctx_alloc(size_t n) {
    ctx_thread *t = ctx_current();
    not_growing(t);
    lock();
    void *p = alloc_locked(t, n);
    unlock();
    return p;
}

// Adapters of `fn` values, one for each inner value and code. Such a value is a named
// function's static record or another of these, so there are finitely many.
void ctx_rec_copy(void *into, uint64_t len, ctx_fn *rec) {
    uint64_t n = ((ctx_task_rec *)rec)->size;
    if (len < n) {
        unplaced();
        ctx_panic_nopos("@record_copy into fewer bytes than the record has");
    }
    memcpy(into, rec, n);
}

ctx_slice ctx_task_name(void *rec) {
    return ((ctx_task_rec *)rec)->name;
}

typedef struct ctx_canon { struct ctx_canon *next; ctx_adapter a; } ctx_canon;

ctx_fn *ctx_adapt(ctx_fn *inner, void (*code)(void)) {
    static ctx_canon *table[256];
    uintptr_t h = (uintptr_t)inner * 31 + (uintptr_t)code;
    h ^= h >> 17;
    ctx_canon **b = &table[(h ^ (h >> 8)) & 255];
    ctx_thread *t = ctx_current();
    not_growing(t);
    lock();
    for (ctx_canon *c = *b; c; c = c->next) {
        if (c->a.inner == inner && c->a.base.code == code) {
            unlock();
            return &c->a.base;
        }
    }
    ctx_canon *c = alloc_locked(t, sizeof *c);
    c->a.base.code = code;
    c->a.inner = inner;
    c->next = *b;
    *b = c;
    unlock();
    return &c->a.base;
}
