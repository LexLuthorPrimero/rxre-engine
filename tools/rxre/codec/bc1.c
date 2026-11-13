#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>
static int g_fast=0;

static uint16_t rgb_to_565(uint8_t r,uint8_t g,uint8_t b){
    return ((r>>3)<<11) | ((g>>2)<<5) | (b>>3);
}
static void _565_to_rgb(uint16_t c, uint8_t* r,uint8_t* g,uint8_t* b){
    uint8_t rr=(c>>11)&0x1f, gg=(c>>5)&0x3f, bb=c&0x1f;
    *r=(rr<<3)|(rr>>2); *g=(gg<<2)|(gg>>4); *b=(bb<<3)|(bb>>2);
}

static int pad(int n){ return ((n+3)/4)*4; }

/* encode a single 4x4 block (16 pixels RGB) -> 8 bytes */
static void encode_block(const uint8_t* px, uint8_t* out) {
    /* exhaustive endpoint search */
    uint16_t best_e0=0,best_e1=0;
    if(g_fast){
        /* fast: min/max by luminance */
        int minidx=0,maxidx=0,minsum=1<<30,maxsum=-1;
        for(int i=0;i<16;i++){
            int sm=px[i*3]+px[i*3+1]+px[i*3+2];
            if(sm<minsum){minsum=sm;minidx=i;}
            if(sm>maxsum){maxsum=sm;maxidx=i;}
        }
        best_e0=rgb_to_565(px[minidx*3],px[minidx*3+1],px[minidx*3+2]);
        best_e1=rgb_to_565(px[maxidx*3],px[maxidx*3+1],px[maxidx*3+2]);
        if(best_e0<best_e1){ uint16_t t=best_e0; best_e0=best_e1; best_e1=t; }
    } else {
    long best_err=1L<<60;
    for(int i=0;i<16;i++){
        for(int j=i+1;j<16;j++){
            uint16_t e0=rgb_to_565(px[i*3],px[i*3+1],px[i*3+2]);
            uint16_t e1=rgb_to_565(px[j*3],px[j*3+1],px[j*3+2]);
            if(e0<e1){ uint16_t t=e0; e0=e1; e1=t; }
            uint8_t r0,g0,b0,r1,g1,b1;
            _565_to_rgb(e0,&r0,&g0,&b0); _565_to_rgb(e1,&r1,&g1,&b1);
            uint8_t pal[4][3];
            pal[0][0]=r0; pal[0][1]=g0; pal[0][2]=b0;
            pal[1][0]=r1; pal[1][1]=g1; pal[1][2]=b1;
            if(e0>e1){
                pal[2][0]=(2*r0+r1)/3; pal[2][1]=(2*g0+g1)/3; pal[2][2]=(2*b0+b1)/3;
                pal[3][0]=(r0+2*r1)/3; pal[3][1]=(g0+2*g1)/3; pal[3][2]=(b0+2*b1)/3;
            } else {
                pal[2][0]=(r0+r1)/2; pal[2][1]=(g0+g1)/2; pal[2][2]=(b0+b1)/2;
                pal[3][0]=0; pal[3][1]=0; pal[3][2]=0;
            }
            long err=0;
            for(int k=0;k<16;k++){
                int be=1<<30;
                for(int c=0;c<4;c++){
                    int d=(px[k*3]-pal[c][0])*(px[k*3]-pal[c][0])+
                          (px[k*3+1]-pal[c][1])*(px[k*3+1]-pal[c][1])+
                          (px[k*3+2]-pal[c][2])*(px[k*3+2]-pal[c][2]);
                    if(d<be) be=d;
                }
                err+=be;
            }
            if(err<best_err){ best_err=err; best_e0=e0; best_e1=e1; }
        }
    }
    }
    /* write endpoints */
    out[0]=best_e0&0xFF; out[1]=(best_e0>>8)&0xFF;
    out[2]=best_e1&0xFF; out[3]=(best_e1>>8)&0xFF;
    /* palette */
    uint8_t r0,g0,b0,r1,g1,b1;
    _565_to_rgb(best_e0,&r0,&g0,&b0); _565_to_rgb(best_e1,&r1,&g1,&b1);
    uint8_t pal[4][3];
    pal[0][0]=r0; pal[0][1]=g0; pal[0][2]=b0;
    pal[1][0]=r1; pal[1][1]=g1; pal[1][2]=b1;
    if(best_e0>best_e1){
        pal[2][0]=(2*r0+r1)/3; pal[2][1]=(2*g0+g1)/3; pal[2][2]=(2*b0+b1)/3;
        pal[3][0]=(r0+2*r1)/3; pal[3][1]=(g0+2*g1)/3; pal[3][2]=(b0+2*b1)/3;
    } else {
        pal[2][0]=(r0+r1)/2; pal[2][1]=(g0+g1)/2; pal[2][2]=(b0+b1)/2;
        pal[3][0]=0; pal[3][1]=0; pal[3][2]=0;
    }
    /* indices */
    uint8_t idx[16];
    for(int k=0;k<16;k++){
        int be=1<<30, best=0;
        for(int c=0;c<4;c++){
            int d=(px[k*3]-pal[c][0])*(px[k*3]-pal[c][0])+
                  (px[k*3+1]-pal[c][1])*(px[k*3+1]-pal[c][1])+
                  (px[k*3+2]-pal[c][2])*(px[k*3+2]-pal[c][2]);
            if(d<be){ be=d; best=c; }
        }
        idx[k]=best;
    }
    /* pack 4 bytes */
    for(int i=0;i<4;i++){
        uint8_t b=0;
        for(int j=0;j<4;j++){
            b |= (idx[i*4+j]&3) << (j*2);
        }
        out[4+i]=b;
    }
}

static void decode_block(const uint8_t* in, uint8_t* out) {
    uint16_t e0=in[0]|(in[1]<<8);
    uint16_t e1=in[2]|(in[3]<<8);
    uint8_t r0,g0,b0,r1,g1,b1;
    _565_to_rgb(e0,&r0,&g0,&b0); _565_to_rgb(e1,&r1,&g1,&b1);
    uint8_t pal[4][3];
    pal[0][0]=r0; pal[0][1]=g0; pal[0][2]=b0;
    pal[1][0]=r1; pal[1][1]=g1; pal[1][2]=b1;
    if(e0>e1){
        pal[2][0]=(2*r0+r1)/3; pal[2][1]=(2*g0+g1)/3; pal[2][2]=(2*b0+b1)/3;
        pal[3][0]=(r0+2*r1)/3; pal[3][1]=(g0+2*g1)/3; pal[3][2]=(b0+2*b1)/3;
    } else {
        pal[2][0]=(r0+r1)/2; pal[2][1]=(g0+g1)/2; pal[2][2]=(b0+b1)/2;
        pal[3][0]=0; pal[3][1]=0; pal[3][2]=0;
    }
    for(int i=0;i<16;i++){
        int bytepos=i/4, bitpos=(i%4)*2;
        int idx=(in[4+bytepos]>>bitpos)&3;
        out[i*3]=pal[idx][0];
        out[i*3+1]=pal[idx][1];
        out[i*3+2]=pal[idx][2];
    }
}

int main(int argc,char**argv){
    if(argc<5){ fprintf(stderr,"usage: %s e|d W H input output\n",argv[0]); return 1; }
    int W=atoi(argv[2]), H=atoi(argv[3]);
    if(W<=0||H<=0){ fprintf(stderr,"bad dims\n"); return 1; }
    FILE* f=fopen(argv[4],"rb"); if(!f){ perror("in"); return 1; }
    fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET);
    /* read W*H*3 bytes */
    int ph=pad(H), pw=pad(W);
    int nblocks=(ph/4)*(pw/4);
    g_fast = (argv[1][0]=='f');
    if(argv[1][0]=='e' || argv[1][0]=='f'){
        size_t expected=(size_t)W*H*3;
        uint8_t* data=malloc(expected);
        size_t rd=fread(data,1,expected,f); fclose(f);
        if(rd!=expected){ fprintf(stderr,"bad input size %zu != %zu\n",rd,expected); return 1; }
        /* pad image */
        uint8_t* padded=calloc(ph*pw*3,1);
        for(int y=0;y<H;y++) for(int x=0;x<W;x++)
            for(int c=0;c<3;c++) padded[(y*pw+x)*3+c]=data[(y*W+x)*3+c];
        uint8_t* out=malloc(nblocks*8);
        for(int by=0;by<ph;by+=4)
            for(int bx=0;bx<pw;bx+=4){
                uint8_t block[4*4*3];
                for(int y=0;y<4;y++) for(int x=0;x<4;x++)
                    for(int c=0;c<3;c++) block[(y*4+x)*3+c]=padded[((by+y)*pw+(bx+x))*3+c];
                encode_block(block, out + ((by/4)*(pw/4)+(bx/4))*8);
            }
        FILE* fo=fopen(argv[5],"wb"); fwrite(out,1,nblocks*8,fo); fclose(fo);
        fprintf(stderr,"encoded %dx%d -> %d bytes\n",W,H,nblocks*8);
        free(padded); free(out);
    } else {
        uint8_t* indata=malloc(nblocks*8);
        FILE* fi=fopen(argv[4],"rb");
        fseek(fi,0,SEEK_END); long fsz=ftell(fi); fseek(fi,0,SEEK_SET);
        if(fsz < nblocks*8){ fprintf(stderr,"truncated input\n"); fclose(fi); free(indata); return 1; }
        fread(indata,1,nblocks*8,fi); fclose(fi);
        uint8_t* out=malloc((size_t)W*H*3);
        uint8_t* padded=calloc(ph*pw*3,1);
        for(int by=0;by<ph;by+=4)
            for(int bx=0;bx<pw;bx+=4){
                uint8_t tmp[4*4*3];
                decode_block(indata+((by/4)*(pw/4)+(bx/4))*8, tmp);
                for(int y=0;y<4;y++) for(int x=0;x<4;x++) for(int c=0;c<3;c++)
                    padded[((by+y)*pw+(bx+x))*3+c]=tmp[(y*4+x)*3+c];
            }
        for(int y=0;y<H;y++) for(int x=0;x<W;x++)
            for(int c=0;c<3;c++) out[(y*W+x)*3+c]=padded[(y*pw+x)*3+c];
        FILE* fo=fopen(argv[5],"wb"); fwrite(out,1,W*H*3,fo); fclose(fo);
        fprintf(stderr,"decoded %dx%d\n",W,H);
        free(indata); free(out); free(padded);
    }
    return 0;
}
