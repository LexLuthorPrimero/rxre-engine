#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>

static int pad(int n){ return ((n+3)/4)*4; }

/* ---------- BC4 ---------- */
static uint8_t bc4_encode_block(const uint8_t* px, uint8_t* out) {
    uint8_t mn=255,mx=0;
    for(int i=0;i<16;i++){ if(px[i]<mn) mn=px[i]; if(px[i]>mx) mx=px[i]; }
    uint8_t e0=mx, e1=mn;
    if(e0<e1){ uint8_t t=e0; e0=e1; e1=t; }
    uint8_t pal[8];
    if(e0>e1){
        pal[0]=e0; pal[1]=e1;
        pal[2]=(6*e0+1*e1)/7; pal[3]=(5*e0+2*e1)/7; pal[4]=(4*e0+3*e1)/7;
        pal[5]=(3*e0+4*e1)/7; pal[6]=(2*e0+5*e1)/7; pal[7]=(1*e0+6*e1)/7;
    } else {
        pal[0]=e0; pal[1]=e1;
        pal[2]=(4*e0+1*e1)/5; pal[3]=(3*e0+2*e1)/5; pal[4]=(2*e0+3*e1)/5;
        pal[5]=(1*e0+4*e1)/5; pal[6]=0; pal[7]=255;
    }
    out[0]=e0; out[1]=e1;
    uint8_t idxb[6]={0,0,0,0,0,0};
    for(int i=0;i<16;i++){
        int be=1<<30, best=0;
        for(int c=0;c<8;c++){
            int d=abs((int)px[i]-pal[c]);
            if(d<be){ be=d; best=c; }
        }
        int bitpos=i*3, bp=bitpos/8, bo=bitpos%8;
        idxb[bp] |= (best & 0x7) << bo;
        if(bo+3>8) idxb[bp+1] |= (best >> (8-bo)) & 0x7;
    }
    for(int i=0;i<6;i++) out[2+i]=idxb[i];
    return 0;
}
static void bc4_decode_block(const uint8_t* in, uint8_t* out) {
    uint8_t e0=in[0], e1=in[1];
    uint8_t pal[8];
    if(e0>e1){
        pal[0]=e0; pal[1]=e1;
        pal[2]=(6*e0+1*e1)/7; pal[3]=(5*e0+2*e1)/7; pal[4]=(4*e0+3*e1)/7;
        pal[5]=(3*e0+4*e1)/7; pal[6]=(2*e0+5*e1)/7; pal[7]=(1*e0+6*e1)/7;
    } else {
        pal[0]=e0; pal[1]=e1;
        pal[2]=(4*e0+1*e1)/5; pal[3]=(3*e0+2*e1)/5; pal[4]=(2*e0+3*e1)/5;
        pal[5]=(1*e0+4*e1)/5; pal[6]=0; pal[7]=255;
    }
    for(int i=0;i<16;i++){
        int bitpos=i*3, bp=bitpos/8, bo=bitpos%8;
        int code=(in[2+bp]>>bo)&0x7;
        if(bo+3>8) code |= (in[2+bp+1]<<(8-bo))&0x7;
        out[i]=pal[code];
    }
}

/* ---------- BC1 (color) ---------- */
static uint16_t rgb_to_565(uint8_t r,uint8_t g,uint8_t b){ return ((r>>3)<<11)|((g>>2)<<5)|(b>>3); }
static void _565_to_rgb(uint16_t c, uint8_t*r,uint8_t*g,uint8_t*b){
    uint8_t rr=(c>>11)&0x1f, gg=(c>>5)&0x3f, bb=c&0x1f;
    *r=(rr<<3)|(rr>>2); *g=(gg<<2)|(gg>>4); *b=(bb<<3)|(bb>>2);
}
/* fast min/max endpoint selection */
static void bc1_encode_block(const uint8_t* px, uint8_t* out) {
    /* find min/max by luminance */
    int minidx=0,maxidx=0,minsum=1<<30,maxsum=-1;
    for(int i=0;i<16;i++){
        int sm=px[i*3]+px[i*3+1]+px[i*3+2];
        if(sm<minsum){minsum=sm;minidx=i;}
        if(sm>maxsum){maxsum=sm;maxidx=i;}
    }
    uint16_t e0=rgb_to_565(px[minidx*3],px[minidx*3+1],px[minidx*3+2]);
    uint16_t e1=rgb_to_565(px[maxidx*3],px[maxidx*3+1],px[maxidx*3+2]);
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
    out[0]=e0&0xFF; out[1]=(e0>>8)&0xFF;
    out[2]=e1&0xFF; out[3]=(e1>>8)&0xFF;
    uint8_t idxb[4]={0,0,0,0};
    for(int k=0;k<16;k++){
        int be=1<<30, best=0;
        for(int c=0;c<4;c++){
            int d=(px[k*3]-pal[c][0])*(px[k*3]-pal[c][0])+
                  (px[k*3+1]-pal[c][1])*(px[k*3+1]-pal[c][1])+
                  (px[k*3+2]-pal[c][2])*(px[k*3+2]-pal[c][2]);
            if(d<be){ be=d; best=c; }
        }
        int bp=k/4, bo=(k%4)*2;
        idxb[bp] |= (best&3)<<bo;
    }
    for(int i=0;i<4;i++) out[4+i]=idxb[i];
}

static void bc1_decode_block(const uint8_t* in, uint8_t* out) {
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
        int bp=i/4, bo=(i%4)*2;
        int idx=(in[4+bp]>>bo)&3;
        out[i*3]=pal[idx][0];
        out[i*3+1]=pal[idx][1];
        out[i*3+2]=pal[idx][2];
    }
}

/* ---------- BC3: 16 bytes = 8 alpha (BC4) + 8 color (BC1) ---------- */
/* ---------- BC5: 16 bytes = 2 x BC4 ---------- */

int main(int argc,char**argv){
    if(argc<7){ fprintf(stderr,"usage: %s e|d fmt W H input output\n",argv[0]); return 1; }
    char mode=argv[1][0];
    const char* fmt=argv[2];
    int W=atoi(argv[3]), H=atoi(argv[4]);
    if(W<=0||H<=0){ fprintf(stderr,"bad dims\n"); return 1; }
    FILE* f=fopen(argv[5],"rb"); if(!f){ perror("in"); return 1; }
    fseek(f,0,SEEK_END); long fsz=ftell(f); fseek(f,0,SEEK_SET);

    if(strcmp(fmt,"bc4")==0){
        if(mode=='e'){
            size_t exp=(size_t)W*H;
            uint8_t* data=malloc(exp);
            if(fread(data,1,exp,f)!=exp){ fprintf(stderr,"bad size\n"); return 1; }
            fclose(f);
            int ph=pad(H),pw=pad(W); int nb=(ph/4)*(pw/4);
            uint8_t* padded=calloc(ph*pw,1);
            for(int y=0;y<H;y++) for(int x=0;x<W;x++) padded[y*pw+x]=data[y*W+x];
            uint8_t* out=malloc(nb*8);
            for(int by=0;by<ph;by+=4) for(int bx=0;bx<pw;bx+=4){
                uint8_t block[16];
                for(int y=0;y<4;y++) for(int x=0;x<4;x++) block[y*4+x]=padded[(by+y)*pw+(bx+x)];
                bc4_encode_block(block, out+((by/4)*(pw/4)+(bx/4))*8);
            }
            FILE* fo=fopen(argv[6],"wb"); fwrite(out,1,nb*8,fo); fclose(fo);
            fprintf(stderr,"bc4 encoded %dx%d -> %d bytes\n",W,H,nb*8);
            free(data); free(padded); free(out);
        } else {
            int ph=pad(H),pw=pad(W); int nb=(ph/4)*(pw/4);
            if(fsz < nb*8){ fprintf(stderr,"truncated\n"); return 1; }
            uint8_t* data=malloc(nb*8);
            fread(data,1,nb*8,f); fclose(f);
            uint8_t* padded=calloc(ph*pw,1);
            int off=0;
            for(int by=0;by<ph;by+=4) for(int bx=0;bx<pw;bx+=4){
                uint8_t tmp[16];
                bc4_decode_block(data+off, tmp); off+=8;
                for(int y=0;y<4;y++) for(int x=0;x<4;x++) padded[(by+y)*pw+(bx+x)]=tmp[y*4+x];
            }
            uint8_t* out=malloc(W*H);
            for(int y=0;y<H;y++) for(int x=0;x<W;x++) out[y*W+x]=padded[y*pw+x];
            FILE* fo=fopen(argv[6],"wb"); fwrite(out,1,W*H,fo); fclose(fo);
            fprintf(stderr,"bc4 decoded %dx%d\n",W,H);
            free(data); free(padded); free(out);
        }
    } else if(strcmp(fmt,"bc1")==0){
        if(mode=='e'){
            size_t exp=(size_t)W*H*3;
            uint8_t* data=malloc(exp);
            if(fread(data,1,exp,f)!=exp){ fprintf(stderr,"bad size\n"); return 1; }
            fclose(f);
            int ph=pad(H),pw=pad(W); int nb=(ph/4)*(pw/4);
            uint8_t* padded=calloc(ph*pw*3,1);
            for(int y=0;y<H;y++) for(int x=0;x<W;x++) for(int c=0;c<3;c++) padded[(y*pw+x)*3+c]=data[(y*W+x)*3+c];
            uint8_t* out=malloc(nb*8);
            for(int by=0;by<ph;by+=4) for(int bx=0;bx<pw;bx+=4){
                uint8_t block[4*4*3];
                for(int y=0;y<4;y++) for(int x=0;x<4;x++) for(int c=0;c<3;c++) block[(y*4+x)*3+c]=padded[((by+y)*pw+(bx+x))*3+c];
                bc1_encode_block(block, out+((by/4)*(pw/4)+(bx/4))*8);
            }
            FILE* fo=fopen(argv[6],"wb"); fwrite(out,1,nb*8,fo); fclose(fo);
            fprintf(stderr,"bc1 encoded %dx%d -> %d bytes\n",W,H,nb*8);
            free(data); free(padded); free(out);
        } else {
            int ph=pad(H),pw=pad(W); int nb=(ph/4)*(pw/4);
            if(fsz < nb*8){ fprintf(stderr,"truncated\n"); return 1; }
            uint8_t* data=malloc(nb*8);
            fread(data,1,nb*8,f); fclose(f);
            uint8_t* padded=calloc(ph*pw*3,1);
            int off=0;
            for(int by=0;by<ph;by+=4) for(int bx=0;bx<pw;bx+=4){
                uint8_t tmp[4*4*3];
                bc1_decode_block(data+off, tmp); off+=8;
                for(int y=0;y<4;y++) for(int x=0;x<4;x++) for(int c=0;c<3;c++)
                    padded[((by+y)*pw+(bx+x))*3+c]=tmp[(y*4+x)*3+c];
            }
            uint8_t* out=malloc(W*H*3);
            for(int y=0;y<H;y++) for(int x=0;x<W;x++) for(int c=0;c<3;c++) out[(y*W+x)*3+c]=padded[(y*pw+x)*3+c];
            FILE* fo=fopen(argv[6],"wb"); fwrite(out,1,W*H*3,fo); fclose(fo);
            fprintf(stderr,"bc1 decoded %dx%d\n",W,H);
            free(data); free(padded); free(out);
        }
    } else if(strcmp(fmt,"bc5")==0){
        /* BC5 = two BC4 channels interleaved per 4x4 block (16 bytes) */
        if(mode=='e'){
            /* input: W*H*2 bytes (two channels interleaved? We expect two separate files? Simplify: input is W*H bytes for ch0, then W*H for ch1 concatenated) */
            size_t exp=(size_t)W*H*2;
            uint8_t* data=malloc(exp);
            if(fread(data,1,exp,f)!=exp){ fprintf(stderr,"bad size (need 2 channels W*H each)\n"); return 1; }
            fclose(f);
            uint8_t* ch0=data; uint8_t* ch1=data+W*H;
            int ph=pad(H),pw=pad(W); int nb=(ph/4)*(pw/4);
            uint8_t* p0=calloc(ph*pw,1); uint8_t* p1=calloc(ph*pw,1);
            for(int y=0;y<H;y++) for(int x=0;x<W;x++){ p0[y*pw+x]=ch0[y*W+x]; p1[y*pw+x]=ch1[y*W+x]; }
            uint8_t* out=malloc(nb*16);
            for(int by=0;by<ph;by+=4) for(int bx=0;bx<pw;bx+=4){
                uint8_t b0[16],b1[16];
                for(int y=0;y<4;y++) for(int x=0;x<4;x++){ b0[y*4+x]=p0[(by+y)*pw+(bx+x)]; b1[y*4+x]=p1[(by+y)*pw+(bx+x)]; }
                int bi=((by/4)*(pw/4)+(bx/4))*16;
                bc4_encode_block(b0, out+bi);
                bc4_encode_block(b1, out+bi+8);
            }
            FILE* fo=fopen(argv[6],"wb"); fwrite(out,1,nb*16,fo); fclose(fo);
            fprintf(stderr,"bc5 encoded %dx%d -> %d bytes\n",W,H,nb*16);
            free(data); free(p0); free(p1); free(out);
        } else {
            int ph=pad(H),pw=pad(W); int nb=(ph/4)*(pw/4);
            if(fsz < nb*16){ fprintf(stderr,"truncated\n"); return 1; }
            uint8_t* data=malloc(nb*16);
            fread(data,1,nb*16,f); fclose(f);
            uint8_t* p0=calloc(ph*pw,1); uint8_t* p1=calloc(ph*pw,1);
            int off=0;
            for(int by=0;by<ph;by+=4) for(int bx=0;bx<pw;bx+=4){
                uint8_t t0[16], t1[16];
                bc4_decode_block(data+off, t0); off+=8;
                bc4_decode_block(data+off, t1); off+=8;
                for(int y=0;y<4;y++) for(int x=0;x<4;x++){ p0[(by+y)*pw+(bx+x)]=t0[y*4+x]; p1[(by+y)*pw+(bx+x)]=t1[y*4+x]; }
            }
            uint8_t* out=malloc(W*H*2);
            for(int y=0;y<H;y++) for(int x=0;x<W;x++){ out[(y*W+x)*2]=p0[y*pw+x]; out[(y*W+x)*2+1]=p1[y*pw+x]; }
            FILE* fo=fopen(argv[6],"wb"); fwrite(out,1,W*H*2,fo); fclose(fo);
            fprintf(stderr,"bc5 decoded %dx%d\n",W,H);
            free(data); free(p0); free(p1); free(out);
        }
    } else if(strcmp(fmt,"bc3")==0){
        /* BC3: 16 bytes = 8 alpha (BC4) + 8 color (BC1) per 4x4 */
        if(mode=='e'){
            size_t exp=(size_t)W*H*4; /* RGBA */
            uint8_t* data=malloc(exp);
            if(fread(data,1,exp,f)!=exp){ fprintf(stderr,"bad size (need RGBA)\n"); return 1; }
            fclose(f);
            int ph=pad(H),pw=pad(W); int nb=(ph/4)*(pw/4);
            uint8_t* rgb=calloc(ph*pw*3,1); uint8_t* alp=calloc(ph*pw,1);
            for(int y=0;y<H;y++) for(int x=0;x<W;x++){
                rgb[(y*pw+x)*3]=data[(y*W+x)*4];
                rgb[(y*pw+x)*3+1]=data[(y*W+x)*4+1];
                rgb[(y*pw+x)*3+2]=data[(y*W+x)*4+2];
                alp[y*pw+x]=data[(y*W+x)*4+3];
            }
            uint8_t* out=malloc(nb*16);
            for(int by=0;by<ph;by+=4) for(int bx=0;bx<pw;bx+=4){
                uint8_t cb[4*4*3], ab[4*4];
                for(int y=0;y<4;y++) for(int x=0;x<4;x++){
                    for(int c=0;c<3;c++) cb[(y*4+x)*3+c]=rgb[((by+y)*pw+(bx+x))*3+c];
                    ab[y*4+x]=alp[(by+y)*pw+(bx+x)];
                }
                int bi=((by/4)*(pw/4)+(bx/4))*16;
                bc4_encode_block(ab, out+bi);       /* alpha first */
                bc1_encode_block(cb, out+bi+8);     /* color second */
            }
            FILE* fo=fopen(argv[6],"wb"); fwrite(out,1,nb*16,fo); fclose(fo);
            fprintf(stderr,"bc3 encoded %dx%d -> %d bytes\n",W,H,nb*16);
            free(data); free(rgb); free(alp); free(out);
        } else {
            int ph=pad(H),pw=pad(W); int nb=(ph/4)*(pw/4);
            if(fsz < nb*16){ fprintf(stderr,"truncated\n"); return 1; }
            uint8_t* data=malloc(nb*16);
            fread(data,1,nb*16,f); fclose(f);
            uint8_t* rgb=calloc(ph*pw*3,1); uint8_t* alp=calloc(ph*pw,1);
            int off=0;
            for(int by=0;by<ph;by+=4) for(int bx=0;bx<pw;bx+=4){
                uint8_t ta[16], tc[4*4*3];
                bc4_decode_block(data+off, ta); off+=8;
                bc1_decode_block(data+off, tc); off+=8;
                for(int y=0;y<4;y++) for(int x=0;x<4;x++){ alp[(by+y)*pw+(bx+x)]=ta[y*4+x]; for(int c=0;c<3;c++) rgb[((by+y)*pw+(bx+x))*3+c]=tc[(y*4+x)*3+c]; }
            }
            uint8_t* out=malloc(W*H*4);
            for(int y=0;y<H;y++) for(int x=0;x<W;x++){
                out[(y*W+x)*4]=rgb[(y*pw+x)*3];
                out[(y*W+x)*4+1]=rgb[(y*pw+x)*3+1];
                out[(y*W+x)*4+2]=rgb[(y*pw+x)*3+2];
                out[(y*W+x)*4+3]=alp[y*pw+x];
            }
            FILE* fo=fopen(argv[6],"wb"); fwrite(out,1,W*H*4,fo); fclose(fo);
            fprintf(stderr,"bc3 decoded %dx%d\n",W,H);
            free(data); free(rgb); free(alp); free(out);
        }
    } else {
        fprintf(stderr,"unknown format %s\n",fmt);
        fclose(f);
        return 1;
    }
    return 0;
}
