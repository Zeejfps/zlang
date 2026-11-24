
#include <stddef.h>
#include <stdint.h>
typedef struct { float r, g, b, a; } Color;
typedef struct { float depth; uint32_t stencil; } DepthStencil;
typedef union { Color color; DepthStencil depth_stencil; } ClearValue;
typedef struct { uint32_t kind; ClearValue value; uint8_t last; } Attachment;
uint64_t ctxtest_size(void) { return sizeof(ClearValue); }
uint64_t ctxtest_align(void) { return _Alignof(ClearValue); }
uint64_t ctxtest_attachment_size(void) { return sizeof(Attachment); }
uint64_t ctxtest_last_offset(void) { return offsetof(Attachment, last); }
ClearValue ctxtest_depth(float d, uint32_t s) { ClearValue v = { 0 }; v.depth_stencil.depth = d; v.depth_stencil.stencil = s; return v; }
float ctxtest_sum(ClearValue v) { return v.color.r + v.color.g + v.color.b + v.color.a; }
uint32_t ctxtest_attachment(Attachment a) { return a.kind * 1000 + a.value.depth_stencil.stencil * 10 + a.last; }
