
#include <stdint.h>
static int32_t add(int32_t a, int32_t b) { return a + b; }
static int32_t mul(int32_t a, int32_t b) { return a * b; }
void *ctxtest_op(int32_t which) { return which == 0 ? (void *)add : which == 1 ? (void *)mul : (void *)0; }
int32_t (*ctxtest_op_typed(int32_t which))(int32_t, int32_t) { return which == 0 ? add : which == 1 ? mul : 0; }
int32_t ctxtest_apply(int32_t (*f)(int32_t, int32_t), int32_t a, int32_t b) { return f(a, b); }
int32_t ctxtest_sub(int32_t a, int32_t b) { return a - b; }
void ctxtest_out(int32_t (*f)(int32_t, int32_t), int32_t *out) { *out = f(20, 22); }
