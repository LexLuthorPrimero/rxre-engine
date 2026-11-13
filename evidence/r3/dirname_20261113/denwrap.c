#define _GNU_SOURCE
/* denwrap.c — R3 etapa 5-bis: reconstrucción independiente de UNA propiedad acotada de /usr/bin/dirname:
 * el nombre de directorio padre acotado. Consumidor: corpus sellado con seeds.
 * Uso: denwrap <input>     → emite stdout (exit 0)
 *      denwrap <corpus> verify  (compara A\tB, total/mismatches) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>

static size_t strip_trailing_slashes(const uint8_t *buf, size_t n) {
    while (n > 0 && buf[n - 1] == '/') n--;
    return n;
}

static void emit_dirname(const uint8_t *in, size_t n, FILE *out) {
    const uint8_t *buf = in;
    /* step 1: strip trailing slashes */
    size_t len = strip_trailing_slashes(buf, n);
    /* handle '.' esoteric case: path is all slashes */
    int leading_slash = (n > 0 && buf[0] == '/');
    if (len == 0) {
        fprintf(out, leading_slash ? "/" : ".");
        fputc('\n', out);
        return;
    }
    /* find last slash in stripped [0, len) */
    size_t last_slash = SIZE_MAX;
    for (size_t i = 0; i < len; i++) if (buf[i] == '/') last_slash = i;
    if (last_slash == SIZE_MAX) {
        fprintf(out, ".\n");
        return;
    }
    /* step 3: prefix = buf[0, last_slash), strip trailing slashes */
    size_t plen = last_slash;
    while (plen > 0 && buf[plen - 1] == '/') plen--;
    if (plen == 0) {
        fprintf(out, leading_slash ? "/" : ".\n");
        return;
    }
    if (leading_slash) {
        fwrite(buf, 1, plen, out);
        fputc('\n', out);
    } else {
        fwrite(buf, 1, plen, out);
        fputc('\n', out);
    }
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

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    if (argc >= 3 && !strcmp(argv[2], "verify")) {
        FILE *cf = fopen(argv[1], "r");
        if (!cf) return 2;
        char line[131072];
        uint8_t a[65536], b[65536]; size_t an, bn;
        unsigned long total = 0, mism = 0;
        while (fgets(line, sizeof line, cf)) {
            char *tab = strchr(line, '\t'); if (!tab) return 2; *tab = '\0';
            char *b0 = tab + 1; char *nl = strchr(b0, '\n'); if (nl) *nl = '\0';
            an = unescape(line, a); bn = unescape(b0, b);
            /* compute expected decision once */
            char tmpbuf[8192];
            size_t o = 0;
            {
                size_t len = an;
                while (len > 0 && a[len-1] == '/') len--;
                int leading = (an > 0 && a[0] == '/');
                if (len == 0) {
                    if (leading) { strcpy(tmpbuf, "/"); } else { strcpy(tmpbuf, "."); }
                } else {
                    size_t last_slash = SIZE_MAX;
                    for (size_t i = 0; i < len; i++) if (a[i] == '/') last_slash = i;
                    if (last_slash == SIZE_MAX) { strcpy(tmpbuf, "."); } else {
                        size_t plen = last_slash;
                        while (plen > 0 && a[plen-1] == '/') plen--;
                        if (plen == 0) { strcpy(tmpbuf, leading ? "/" : "."); }
                        else { memcpy(tmpbuf, a, plen); tmpbuf[plen] = 0; }
                    }
                }
                o = strlen(tmpbuf);
            }
            total++;
            if (o != bn || memcmp(tmpbuf, b, bn) != 0) mism++;
        }
        fclose(cf);
        printf("total=%lu mismatches=%lu\n", total, mism);
        return mism ? 1 : 0;
    }
    FILE *in = fopen(argv[1], "rb");
    if (!in) return 2;
    uint8_t buf[65536]; size_t n = fread(buf, 1, sizeof buf, in);
    fclose(in);
    emit_dirname(buf, n, stdout);
    return 0;
}
