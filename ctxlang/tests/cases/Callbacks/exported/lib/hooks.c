// Calls the program's `#c_export` fns by their symbols, which the program defines.
#include <stdint.h>

typedef struct { int32_t x, y; } P;

int32_t game_add(int32_t a, int32_t b);
void game_tick(uint64_t frame);
P game_swap(P p);
void game_count(int64_t *total, int32_t by);
int32_t game_any(int32_t n);
int32_t game_check(int32_t n);

int32_t ctxtest_hooks(int32_t (*add)(int32_t, int32_t)) {
    int32_t sum = game_add(40, 2);
    game_tick(7);
    game_tick(8);
    P q = game_swap((P){ 1, 2 });
    int64_t total = 0;
    game_count(&total, 5);
    game_count(&total, 6);
    // The program's pointer to game_add is the exported function itself.
    int32_t same = add == game_add;
    return sum * 1000000 + (q.x * 10 + q.y) * 10000 + (int32_t)total * 10 + same + game_any(-1);
}

int32_t ctxtest_checks(int32_t count) {
    int32_t sum = 0;
    for (int32_t i = 0; i < count; i++) sum += game_check(i);
    return sum;
}
