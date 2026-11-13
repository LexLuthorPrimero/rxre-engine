#define _GNU_SOURCE
/* foldwrap.c — R3 etapa 3: reconstrucción independiente de la semántica de ancho de fold
 * acotada: avance de columnas con tab stop 8, EAW W/F=2, CELL WIDTHS por codepoint,
 * saltos de línea después de w celdas exactas, nunca rompe dentro de un codepoint.
 * Uso: foldwrap <input-file>         (emite stdout, exit 0)
 *      foldwrap <cases-with-tab> <matrix-path>   (modo verify: compara y cuenta) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <locale.h>
#include <wchar.h>
#include <unistd.h>
#include <fcntl.h>

/* Widths: 2 for East Asian Wide/Fullwidth; 0 for combining/Cf/Cc/Cs/Cn/Co/jamo-conjoining;
 * 1 otherwise; TAB advances to next multiple of 8. Mirrors the observed oracle behaviour
 * independently (not transcribed from any source code). */
static int east_asian_wide(wchar_t cp) {
    if (cp >= 0x1100 && cp <= 0x115F) return 2;   /* Hangul choseong */
    if (cp >= 0x2E80 && cp <= 0xA4CF) return 2;   /* CJK radicals/ideographs */
    if (cp >= 0xA960 && cp <= 0xA97C) return 2;   /* Hangul jamo extended-A choseong */
    if (cp >= 0xAC00 && cp <= 0xD7A3) return 2;   /* Hangul syllables */
    if (cp >= 0xF900 && cp <= 0xFAFF) return 2;   /* CJK compat ideographs */
    if (cp >= 0xFE30 && cp <= 0xFE66) return 2;   /* CJK compat forms */
    if (cp >= 0xFF00 && cp <= 0xFF60) return 2;   /* fullwidth forms */
    if (cp >= 0xFFE0 && cp <= 0xFFE6) return 2;
    if (cp >= 0x30000 && cp <= 0x3134A) return 2; /* CJK Ext G */
    if (cp >= 0x31350 && cp <= 0x33479) return 2;
    if (cp >= 0x20000 && cp <= 0x2A6DF) return 2;
    if (cp >= 0x2A700 && cp <= 0x2E7FF) return 2;
    return 0;
}
static int is_zero_width(wchar_t cp) {
    if (cp >= 0x1160 && cp <= 0x11FF) return 1;   /* conjoining jamo */
    if (cp == 0x00AD) return 0;                   /* soft hyphen quirk: 1 cell */
    if (cp >= 0x0300 && cp <= 0x036F) return 1;   /* Mn combining */
    if (cp >= 0x0483 && cp <= 0x0489) return 1;
    if (cp >= 0x20B9 && cp <= 0x20CF) return 1;
    if (cp >= 0x200B && cp <= 0x200F) return 1;   /* zero-width space/joiners/marks */
    if (cp >= 0x202A && cp <= 0x202F) return 1;
    if (cp >= 0x2060 && cp <= 0x2069) return 1;   /* word joiner .. isolates */
    if (cp >= 0xFFFE && cp <= 0xFFFF) return 1;
    return 0;
}
static int cell_width(wchar_t cp) {
    if (cp == L'\t') return -1; /* sentinel: advance to next 8-stop */
    if (is_zero_width(cp)) return 0;
    if (east_asian_wide(cp)) return 2;
    /* control chars and other non-printables: 0 cells (trailing/embedded after content
     * never advance the column counter except NUL path; observed behaviour) */
    if (cp < 0x20 && cp != L'\n' && cp != L'\r') return 0;
    if (cp >= 0x7F && cp <= 0x9F) return 0;
    return 1;
}

/* decode one escaped byte sequence level: inputs are raw utf-8 in the file for verify,
 * we read raw bytes directly here (escapes only in the corpus files for humans). */
static void emit_fold(const uint8_t *buf, size_t len, int w, FILE *out) {
    size_t i = 0;
    int col = 0;
    int line_has_content = 0;
    while (i < len) {
        unsigned char b = buf[i];
        wchar_t cp = 0; int nb = 1;
        if (b < 0x80) { cp = b; nb = 1; }
        else if ((b & 0xE0) == 0xC0) { cp = ((b & 0x1F) << 6) | (buf[i+1] & 0x3F); nb = 2; }
        else if ((b & 0xF0) == 0xE0) { cp = ((b & 0x0F) << 12) | ((buf[i+1] & 0x3F) << 6) | (buf[i+2] & 0x3F); nb = 3; }
        else if ((b & 0xF8) == 0xF0) { cp = ((b & 0x07) << 18) | ((buf[i+1] & 0x3F) << 12) | ((buf[i+2] & 0x3F) << 6) | (buf[i+3] & 0x3F); nb = 4; }
        /* advance cells for this cp; wrapping happens BEFORE placing the cp */
        int cw = cell_width(cp);
        int advance = 0;
        if (cw == -1) { /* tab: advance to next multiple of 8; never wraps by itself */
            int target = ((col + 1 + 7) / 8) * 8;
            if (target > w && line_has_content) {
                fputc('\n', out);
                col = 0;
                line_has_content = 0;
                target = 8;
            }
            fputc('\t', out);
            col = target;
            line_has_content = 1;
            i += nb; continue;
        }
        if (cp == L'\n') {
            fputc('\n', out);
            col = 0;
            line_has_content = 0;
            i += nb;
            continue;
        }
        advance = cw;
        if (col + advance > w && line_has_content) {
            fputc('\n', out);
            col = 0;
            line_has_content = 0;
        }
        /* emit the codepoint bytes */
        for (size_t k = 0; k < (size_t)nb; k++) fputc(buf[i + k], out);
        col += advance;
        line_has_content = 1;
        i += nb;
    }
}


/* verify mode: corpus has lines A\tB where A and B are \xHH-escaped */
static size_t unescape(const char *src, uint8_t out[65536]) {
    size_t o = 0;
    for (size_t i = 0; src[i];) {
        if (src[i] == '\\' && src[i+1] == 'x') {
            unsigned v = 0;
            char c;
            for (int k = 0; k < 2 && (c = src[i+2+k]); k++) {
                v <<= 4;
                if (c >= '0' && c <= '9') v |= (unsigned)(c - '0');
                else if (c >= 'a' && c <= 'f') v |= (unsigned)(c - 'a' + 10);
                else if (c >= 'A' && c <= 'F') v |= (unsigned)(c - 'A' + 10);
                else return 0;
            }
            out[o++] = (uint8_t)v; i += 4;
        } else out[o++] = (uint8_t)src[i++];
    }
    return o;
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    if (argc == 3) {
        /* verify mode */
        FILE *cf = fopen(argv[1], "r");
        if (!cf) return 2;
        char line[131072];
        uint8_t a[65536], b[65536]; size_t an, bn;
        unsigned long total = 0, mism = 0;
        while (fgets(line, sizeof line, cf)) {
            char *tab = strchr(line, '\t'); if (!tab) return 2; *tab = '\0';
            char *b0 = tab + 1; char *nl = strchr(b0, '\n'); if (nl) *nl = '\0';
            an = unescape(line, a); bn = unescape(b0, b);
            /* reconstruct output bytes for A */
            /* write A to temp, run internal emission, compare */
            char tmp[] = "/tmp/foldwrap_vfXXXXXX";
            int fd = mkstemp(tmp);
            if (fd < 0) return 2;
            FILE *tf = fdopen(fd, "w+b");
            emit_fold(a, an, 4, tf);
            fflush(tf);
            /* read back */
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
    emit_fold(buf, n, 4, stdout);
    return 0;
}
