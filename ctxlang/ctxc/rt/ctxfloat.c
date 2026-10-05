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

// repr(v) for a double, with ".0" added to whole numbers: shortest digits that read back as v,
// in exponent form when the decimal exponent is below -4 or above 15.
static int repr_f64(double v, char *out) {
    if (isnan(v)) return sprintf(out, "nan");
    if (isinf(v)) return sprintf(out, v < 0 ? "-inf" : "inf");
    if (v == 0) return sprintf(out, signbit(v) ? "-0.0" : "0.0");
    char buf[64];
    int p;
    for (p = 1; p < 17; p++) {
        snprintf(buf, sizeof buf, "%.*e", p - 1, v);
        if (ctx_strtod(buf, NULL) == v) break;
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

// The shortest '%.Ng' text that reads back as v through a double, as ctxi's _shortest_f32, plus
// ".0" if it has neither '.' nor 'e'.
static int repr_f32(float v, char *out) {
    if (isnan(v)) return sprintf(out, "nan");
    if (isinf(v)) return sprintf(out, v < 0 ? "-inf" : "inf");
    int p, n = 0;
    for (p = 1; p <= 9; p++) {
        n = snprintf(out, 64, "%.*g", p, (double)v);
        if ((float)ctx_strtod(out, NULL) == v) break;
    }
    if (p > 9) n = snprintf(out, 64, "%.9g", (double)v);
    if (!strchr(out, '.') && !strchr(out, 'e')) {
        strcpy(out + n, ".0");
        n += 2;
    }
    return n;
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
