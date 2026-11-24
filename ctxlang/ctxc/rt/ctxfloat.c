// ctxfloat: floats as text and back, exactly as Python has them, for std's ascii (std/ascii.ctx)
// and for ctxrt.h's float-to-integer @as when it fails. Written against mingw-w64 (Windows) and
// POSIX, over the C library's printf and strtod. A program links it only if its C uses one of
// its functions, all named ctx_float_ or ctx_f2i_ (ctxc/drive.ctx, `uses_float`).

#define __USE_MINGW_ANSI_STDIO 1     // C99 printf: two-digit exponents, %llu
#include "ctxrt.h"

#include <stdio.h>
#include <stdlib.h>

#ifdef _WIN32
#define ctx_strtod __mingw_strtod     // correctly rounded, unlike msvcrt's
#define ctx_strtof __mingw_strtof
#else
#define ctx_strtod strtod
#define ctx_strtof strtof
#endif

// A float's text (spec §13, Formatting, rule 9), which is Python's repr of a double: the
// shortest digits that read back as v, as a double or with `single` as a float, written plainly
// with a point (`100.0`, `0.001`), a ".0" after a whole number, and in exponent form
// (`1e+16`, `1.5e-05`) when the value is below 1e-4 or from 1e16 up.
static int repr(double v, int single, char *out) {
    if (isnan(v)) return sprintf(out, "nan");
    if (isinf(v)) return sprintf(out, v < 0 ? "-inf" : "inf");
    if (v == 0) return sprintf(out, signbit(v) ? "-0.0" : "0.0");
    char buf[64];
    int p, most = single ? 9 : 17;
    for (p = 1; p < most; p++) {
        snprintf(buf, sizeof buf, "%.*e", p - 1, v);
        if (single ? ctx_strtof(buf, NULL) == (float)v : ctx_strtod(buf, NULL) == v) break;
    }
    snprintf(buf, sizeof buf, "%.*e", p - 1, v);
    // buf is [-]D[.DDD]e[+-]XX
    char digits[32];
    int nd = 0, i = 0, neg = 0;
    if (buf[i] == '-') { neg = 1; i++; }
    for (; buf[i] != 'e'; i++)
        if (buf[i] != '.') digits[nd++] = buf[i];
    while (nd > 1 && digits[nd - 1] == '0') nd--;
    int exp = atoi(buf + i + 1);
    int decpt = exp + 1;
    char *o = out;
    if (neg) *o++ = '-';
    if (decpt <= -4 || decpt > 16) {
        *o++ = digits[0];
        if (nd > 1) {
            *o++ = '.';
            memcpy(o, digits + 1, nd - 1);
            o += nd - 1;
        }
        o += sprintf(o, "e%c%02d", exp < 0 ? '-' : '+', exp < 0 ? -exp : exp);
    } else if (decpt <= 0) {
        *o++ = '0';
        *o++ = '.';
        for (int k = 0; k < -decpt; k++) *o++ = '0';
        memcpy(o, digits, nd);
        o += nd;
    } else if (decpt >= nd) {
        memcpy(o, digits, nd);
        o += nd;
        for (int k = 0; k < decpt - nd; k++) *o++ = '0';
        *o++ = '.';
        *o++ = '0';
    } else {
        memcpy(o, digits, decpt);
        o += decpt;
        *o++ = '.';
        memcpy(o, digits + decpt, nd - decpt);
        o += nd - decpt;
    }
    *o = 0;
    return (int)(o - out);
}

static int repr_f64(double v, char *out) {
    return repr(v, 0, out);
}

// An f32's digits are the shortest that read back as it, an f32: fewer than its double's.
static int repr_f32(float v, char *out) {
    return repr((double)v, 1, out);
}

static uint64_t put_digits(const char *text, int n, ctx_slice into) {
    if ((uint64_t)n > into.len) {
        char msg[128];
        snprintf(msg, sizeof msg, "%d characters do not fit in a buffer of %llu", n, (unsigned long long)into.len);
        ctx_panic_nopos(msg);
    }
    memcpy(into.ptr, text, n);
    return (uint64_t)n;
}

uint64_t ctx_float_f64_digits(double v, ctx_slice into) {
    char buf[64];
    return put_digits(buf, repr_f64(v, buf), into);
}

uint64_t ctx_float_f32_digits(float v, ctx_slice into) {
    char buf[64];
    return put_digits(buf, repr_f32(v, buf), into);
}

// v with `precision` digits after the point, at most 30: C's "%.*f", which rounds the exact
// value to nearest, a halfway case to the even digit, and keeps a zero's sign.
uint64_t ctx_float_f64_fixed(double v, uint32_t precision, ctx_slice into) {
    char buf[352];
    int n;
    if (isnan(v)) n = sprintf(buf, "nan");
    else if (isinf(v)) n = sprintf(buf, v < 0 ? "-inf" : "inf");
    else n = snprintf(buf, sizeof buf, "%.*f", precision > 30 ? 30 : (int)precision, v);
    return put_digits(buf, n, into);
}

// text as a C string: on the stack if it is short, as float syntax is, else from malloc.
static double parse(ctx_slice text, int single) {
    char small[128];
    char *s = text.len < sizeof small ? small : malloc(text.len + 1);
    if (!s) ctx_panic_nopos("out of memory");
    if (text.len) memcpy(s, text.ptr, text.len);
    s[text.len] = 0;
    double v = single ? (double)ctx_strtof(s, NULL) : ctx_strtod(s, NULL);
    if (s != small) free(s);
    return v;
}

double ctx_float_f64_parse(ctx_slice text) {
    return parse(text, 0);
}

float ctx_float_f32_parse(ctx_slice text) {
    return (float)parse(text, 1);
}

_Noreturn void ctx_f2i_fail(double v, const char *dst, CTX_POS) {
    char text[64], msg[128];
    repr_f64(v, text);
    snprintf(msg, sizeof msg, "@as: %s is not representable in %s", text, dst);
    ctx_panic(line, col, file, msg);
}
