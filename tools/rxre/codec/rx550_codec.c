#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>

/* Simple RLE codec for byte streams (lossless). Block-based. */
/* Format: [4-byte original size][blocks: (count, byte) where count 0..255, if count==0 end] */

static int compress(const uint8_t* in, size_t inlen, uint8_t** out, size_t* outlen) {
    size_t cap = inlen*2 + 8;
    uint8_t* buf = malloc(cap);
    if(!buf) return -1;
    size_t pos=0;
    /* write original size */
    for(int i=0;i<4;i++){ buf[pos++] = (inlen>>(i*8))&0xFF; }
    size_t i=0;
    while(i<inlen) {
        uint8_t b=in[i];
        size_t run=1;
        while(i+run<inlen && in[i+run]==b && run<255) run++;
        buf[pos++]= (uint8_t)run;
        buf[pos++]= b;
        i+=run;
    }
    buf[pos++]=0; /* terminator */
    *out=buf; *outlen=pos;
    return 0;
}

static int decompress(const uint8_t* in, size_t inlen, uint8_t** out, size_t* outlen) {
    if(inlen<4) return -1;
    size_t orig=0;
    for(int i=0;i<4;i++) orig |= (size_t)in[i]<<(i*8);
    uint8_t* buf=malloc(orig+1);
    if(!buf) return -1;
    size_t pos=4, o=0;
    while(pos<inlen) {
        uint8_t cnt=in[pos++];
        if(cnt==0) break;
        if(pos>=inlen) { free(buf); return -1; }
        uint8_t b=in[pos++];
        for(uint8_t k=0;k<cnt;k++){
            if(o>=orig){ free(buf); return -1; }
            buf[o++]=b;
        }
    }
    if(o!=orig){ free(buf); return -1; }
    *out=buf; *outlen=o;
    return 0;
}

int main(int argc, char** argv) {
    if(argc<4){ fprintf(stderr,"usage: %s c|d input output\n",argv[0]); return 1; }
    FILE* f=fopen(argv[2],"rb");
    if(!f){ perror("input"); return 1; }
    fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET);
    uint8_t* data=malloc(sz);
    fread(data,1,sz,f); fclose(f);
    uint8_t* out; size_t outlen;
    clock_t t0=clock();
    int rc;
    if(argv[1][0]=='c') rc=compress(data,sz,&out,&outlen);
    else rc=decompress(data,sz,&out,&outlen);
    clock_t t1=clock();
    if(rc!=0){ fprintf(stderr,"error\n"); return 1; }
    FILE* fo=fopen(argv[3],"wb");
    fwrite(out,1,outlen,fo); fclose(fo);
    double ms=(double)(t1-t0)/CLOCKS_PER_SEC*1000.0;
    fprintf(stderr,"%s: %ld -> %zu bytes (%.2f ms)\n", argv[1], sz, outlen, ms);
    free(data); free(out);
    return 0;
}
