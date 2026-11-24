
#include <stdint.h>
#include <string.h>
typedef struct { const char *name; int32_t n; } Named;
typedef const char *(*Pick)(int32_t);
static const char *pick(int32_t i) { return i ? "one" : NULL; }
uint64_t ctxtest_named(Named x) { return x.name ? strlen(x.name) * 10 + (uint64_t)x.n : (uint64_t)x.n; }
const char *ctxtest_echo(const char *s) { return s; }
Pick ctxtest_picker(void) { return pick; }
