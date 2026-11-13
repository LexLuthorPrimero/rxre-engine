#define _GNU_SOURCE
/* basewrap.c — R3 etapa 6: reconstrucción independiente de UNA propiedad acotada de /usr/bin/basename:
 * el último componente acotado. Consumidor: corpus sellado con seeds.
 * Uso: basewrap <input>     → emite stdout (exit 0)
 *      basewrap <corpus> verify  (compara A\tB, total/mismatches) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
#include <unistd.h>
#include <fcntl.h>

static size_t strip_trailing_slashes(const uint8_t *buf, size_t n) {
    while (n > 0 && buf[n - 1] == '/') n--;
    return n;
}

static void emit_basename(const uint8_t *in, size_t n, FILE *out) {
    const uint8_t *buf = in;
    size_t len = strip_trailing_slashes(buf, n);
    int leading_slash = (n > 0 && buf[0] == '/');
    if (len == 0) {
        fprintf(out, leading_slash ? "/" : ".");
        fputc('\n', out);
        return;
    }
    size_t last_slash = SIZE_MAX;
    for (size_t i = 0; i < len; i++) if (buf[i] == '/') last_slash = i;
    if (last_slash == SIZE_MAX) {
        fwrite(buf, 1, len, out);
        fputc('\n', out);
        return;
    }
    const uint8_t *comp = buf + last_slash + 1;
    size_t clen = len - last_slash - 1;
    fwrite(comp, 1, clen, out);
    fputc('\n', out);
}

static size_t unescape(const char *src, uint8_t out[65536]) {
    size_t o = 0;
    for (size_t i = 0; src[i] && src[i+1] && src[i+2] && src[i+3];) {
        if (src[i] == '\\' && src[i+1] == 'x') {
            unsigned v = 0;
            for (int k = 0; k < 2; k++) {
                char c = src[i + 2 + k];
                v <<= 4;
                if (c >= '0' && c <= '9') v |= (unsigned)(c - '0');
                else if (c >= 'a' && c <= 'f') v |= (unsigned)(c - 'a' + 10);
                else if (c >= 'A' && c <= 'F') v |= (unsigned)(c - 'A' + 10);
                else return 0;
            }
            out[o++] = (uint8_t)v; i += 4;
        } else { out[o++] = (uint8_t)src[i++]; }
    }
    return o;
}

static size_t expected_basename(const uint8_t *a, size_t an, uint8_t out[65536]) {
    size_t len = strip_trailing_slashes(a, an);
    int leading_slash = (an > 0 && a[0] == '/');
    if (len == 0) {
        out[0] = leading_slash ? '/' : '.';
        return 1;
    }
    size_t last_slash = SIZE_MAX;
    for (size_t i = 0; i < len; i++) if (a[i] == '/') last_slash = i;
    if (last_slash == SIZE_MAX) {
        memcpy(out, a, len);
        return len;
    }
    size_t clen = len - last_slash - 1;
    memcpy(out, a + last_slash + 1, clen);
    return clen;
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    if (argc >= 3 && !strcmp(argv[2], "verify")) {
        FILE *cf = fopen(argv[1], "r");
        if (!cf) return 2;
        char line[131072];
        uint8_t a[65536], b[65536], exp[65536];
        unsigned long total = 0, mism = 0;
        while (fgets(line, sizeof line, cf)) {
            char *tab = strchr(line, '\t'); if (!tab) return 2; *tab = '\0';
            char *b0 = tab + 1; char *nl = strchr(b0, '\n'); if (nl) *nl = '\0';
            size_t an = unescape(line, a); size_t bn = unescape(b0, b);
            size_t en = expected_basename(a, an, exp);
            total++;
            if (en != bn || memcmp(exp, b, bn) != 0) mism++;
        }
        fclose(cf);
        printf("total=%lu mismatches=%lu\n", total, mism);
        return mism ? 1 : 0;
    }
    FILE *in = fopen(argv[1], "rb");
    if (!in) return 2;
    uint8_t buf[65536]; size_t n = fread(buf, 1, sizeof buf, in);
    fclose(in);
    emit_basename(buf, n, stdout);
    return 0;
}
