// ctxthread: the runtime's part of threads (ctxrt.h, threads), which a program links only if it
// is threaded (spec §15, Entry point, rule 8): ctxc's driver links it when the program's C
// names a ctx_thread_ function (ctxc/drive.ctx, uses_threads). It keeps a pointer to each
// thread's state, which a thread's first callback gives it (ctx_thread_enter), and calls no
// thread library: std starts threads (std/thread.ctx, over std/os).

#define CTX_THREADS 1
#include "ctxrt.h"

#if defined(_WIN64) && defined(__x86_64__)

// A TLS slot of kernel32's, read through the TEB as CTX_HERE does.
__declspec(dllimport) unsigned long __stdcall TlsAlloc(void);
__declspec(dllimport) int __stdcall TlsSetValue(unsigned long index, void *value);
__declspec(dllimport) void *__stdcall TlsGetValue(unsigned long index);

uint32_t ctx_thread_slot, ctx_thread_limit_slot;

static ctx_thread *here(void) { return (ctx_thread *)TlsGetValue(ctx_thread_slot); }
static void set_here(ctx_thread *t) { TlsSetValue(ctx_thread_slot, t); }
static void set_limit(uint64_t limit) { TlsSetValue(ctx_thread_limit_slot, (void *)(uintptr_t)limit); }

static uint32_t new_slot(void) {
    unsigned long slot = TlsAlloc();
    if (slot >= 64) __builtin_trap();       // only the TEB's own 64 slots are read directly
    return (uint32_t)slot;
}

static void make_slot(void) {
    ctx_thread_slot = new_slot();
    ctx_thread_limit_slot = new_slot();
}

#else

_Thread_local ctx_thread *ctx_thread_current;
_Thread_local uint64_t ctx_thread_limit;

static ctx_thread *here(void) { return ctx_thread_current; }
static void set_here(ctx_thread *t) { ctx_thread_current = t; }
static void set_limit(uint64_t limit) { ctx_thread_limit = limit; }
static void make_slot(void) {}

#endif

void ctx_thread_setup(void) {
    make_slot();
    set_here(&ctx_main_thread);
    ctx_current = here;
    ctx_threaded = 1;
}

int ctx_thread_enter(ctx_thread *t) {
    if (here()) return 0;
    char *p = (char *)t;
    for (uint64_t i = 0; i < sizeof *t; i++) p[i] = 0;
    set_here(t);
    set_limit(0);
    return 1;
}

void ctx_thread_leave(ctx_thread *t) {
    if (ctx_thread_ends) ctx_thread_ends();
    ctx_rec_give(t);
    set_here(NULL);
}

void ctx_thread_begin(uint64_t usable, ctx_slice name) {
    ctx_thread *t = here();
    uint64_t at = (uint64_t)(uintptr_t)__builtin_frame_address(0);
    set_limit(at > usable ? at - usable : 0);
    uint64_t n = name.len < sizeof t->name ? name.len : sizeof t->name - 1;
    const char *s = name.ptr;
    for (uint64_t i = 0; i < n; i++) t->name[i] = s[i];
    t->name[n] = 0;
    t->name_len = n;
}
