
#include <stdint.h>
int32_t ctxtest_apply(int32_t (*f)(int32_t, int32_t), int32_t a, int32_t b) { return f(a, b); }
void ctxtest_each(void (*f)(int64_t *, int32_t), int64_t *user, int32_t n) {
    for (int32_t i = 1; i <= n; i++) f(user, i);
}
typedef struct { int32_t x, y; } P;
P ctxtest_swap(P (*f)(P), P p) { return f(p); }
