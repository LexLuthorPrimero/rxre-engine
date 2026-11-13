#define _GNU_SOURCE
/* trwrap.c — R3 etapa 5: reconstrucción independiente de UNA propiedad acotada de /usr/bin/tr:
 * `tr -s x` — colapso de runs consecutivos de byte 0x78 a un único byte (squeeze).
 * Nada más: no -c, no -d, no -s con conjunto multi-char, no unicode handling, no clases.
 * Uso: trwrap <input-file>        → emite stdout (exit 0)
 *      trwrap <corpus> [B-verify] → modo verify: compara A-vs-B, total/mismatches */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>

static void emit_squeeze(const uint8_t *buf, size_t len, FILE *out) {
    int prev_x = 0;
    for (size_t i = 0; i < len; i++) {
        int is_x = (buf[i] == 0x78); /* 'x' */
        if (is_x && prev_x) continue;   /* run continues: drop extra x */
        fputc(buf[i], out);
        prev_x = is_x;
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
            char tmp[] = "/tmp/trwrap_vfXXXXXX";
            int fd = mkstemp(tmp);
            if (fd < 0) return 2;
            FILE *tf = fdopen(fd, "w+b");
            emit_squeeze(a, an, tf);
            fflush(tf);
            fseek(tf, 0, SEEK_SET);
            uint8_t got[65536]; size_t gn = fread(got, 1, sizeof got, tf);
            fclose(tf);
            unlink(tmp);
            total++;
            if (gn != bn || memcmp(got, b, bn) != 0) mism++;
        }
        fclose(cf);
        printf("total=%lu mismatches=%lu\n", total, mism);
        return mism ? 1 : 0;
    }
    FILE *in = fopen(argv[1], "rb");
    if (!in) return 2;
    uint8_t buf[65536]; size_t n = fread(buf, 1, sizeof buf, in);
    fclose(in);
    emit_squeeze(buf, n, stdout);
    return 0;
}
