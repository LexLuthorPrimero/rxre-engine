/* clean-room harness: verify2 <corpus> <matrix> ; compares filenvercmp vs matrix ints. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
extern int filenvercmp(const char *, const char *);
static size_t unescape(const char *src, uint8_t out[4096]) {
    size_t o = 0;
    for (size_t i = 0; src[i]; ) {
        if (src[i] == '\\' && src[i+1] == 'x') {
            unsigned v = 0;
            for (int k = 0; k < 2; k++) { char c = src[i+2+k]; v <<= 4;
                if (c >= '0' && c <= '9') v |= (unsigned)(c - '0'); else if (c >= 'a' && c <= 'f') v |= (unsigned)(c - 'a' + 10); else if (c >= 'A' && c <= 'F') v |= (unsigned)(c - 'A' + 10); }
            out[o++] = (uint8_t)v; i += 4;
        } else out[o++] = (uint8_t)src[i++];
    }
    return o;
}
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    FILE *cases = fopen(argv[1], "rb"), *expected = fopen(argv[2], "rb");
    if (!cases || !expected) return 2;
    char line[16384]; uint8_t a[4096], b[4096]; char abuf[4096], bbuf[4096];
    size_t n = 0, mism = 0;
    while (fgets(line, sizeof line, cases)) {
        char *tab = strchr(line, '\t'); if (!tab) return 2; *tab = '\0';
        char *a0 = line, *b0 = tab + 1; char *nl = strchr(b0, '\n'); if (nl) *nl = '\0';
        size_t alen = unescape(a0, a); size_t blen = unescape(b0, b);
        memcpy(abuf, a, alen); abuf[alen] = '\0';
        memcpy(bbuf, b, blen); bbuf[blen] = '\0';
        int rc = filenvercmp(abuf, bbuf);
        char exp[64]; if (!fgets(exp, sizeof exp, expected)) return 2;
        int e = atoi(exp);
        if (rc != e) mism++;
        n++;
    }
    printf("total=%zu mismatches=%zu\n", n, mism);
    return mism ? 1 : 0;
}
