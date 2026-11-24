#include <stdlib.h>
#include <stdio.h>
#include "ctxrt.h"
static char *base;
static void check(void) {
    if (ctx_recs.seg->next != NULL || ctx_recs.top != base) {
        fprintf(stderr, "records not released\n");
        abort();
    }
}
__attribute__((constructor)) static void install(void) { base = ctx_recs.top; atexit(check); }
