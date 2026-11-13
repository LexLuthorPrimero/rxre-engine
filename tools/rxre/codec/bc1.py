#!/usr/bin/env python3
"""BC1 (DXT1) encoder/decoder for RGB/RGBA textures."""
import struct, numpy as np

def rgb_to_565(r,g,b):
    r,g,b=int(r),int(g),int(b)
    return ((r>>3)<<11) | ((g>>2)<<5) | (b>>3)

def _565_to_rgb(c):
    r=(c>>11)&0x1f; g=(c>>5)&0x3f; b=c&0x1f
    r=(r<<3)|(r>>2); g=(g<<2)|(g>>4); b=(b<<3)|(b>>2)
    return r,g,b

def _pad_dim(n): return ((n+3)//4)*4

def encode_bc1(img):
    # img: numpy array HxWx3 or HxWx4 (uint8)
    h,w = img.shape[:2]
    has_alpha = img.shape[2]==4
    ph=_pad_dim(h); pw=_pad_dim(w)
    # pad
    padded=np.zeros((ph,pw,img.shape[2]),dtype=np.uint8)
    padded[:h,:w]=img
    blocks=[]
    for by in range(0,ph,4):
        for bx in range(0,pw,4):
            block=padded[by:by+4,bx:bx+4,:3]
            # flatten
            pixels=block.reshape(-1,3)
            # find min/max by luminance or just min/max per channel? Use simple: endpoints = min and max color
            # exhaustive endpoint search over pixel pairs
            best_err=1e18; best_e0=0; best_e1=0
            for i in range(16):
                for j in range(i+1,16):
                    e0=rgb_to_565(*pixels[i]); e1=rgb_to_565(*pixels[j])
                    if e0<e1: e0,e1=e1,e0
                    r0,g0,b0=_565_to_rgb(e0); r1,g1,b1=_565_to_rgb(e1)
                    if e0>e1:
                        pal=[(r0,g0,b0),(r1,g1,b1),((2*r0+r1)//3,(2*g0+g1)//3,(2*b0+b1)//3),((r0+2*r1)//3,(g0+2*g1)//3,(b0+2*b1)//3)]
                    else:
                        pal=[(r0,g0,b0),(r1,g1,b1),((r0+r1)//2,(g0+g1)//2,(b0+b1)//2),(0,0,0)]
                    err=0
                    for p in pixels:
                        be=min(int(p[0]-c[0])**2+int(p[1]-c[1])**2+int(p[2]-c[2])**2 for c in pal)
                        err+=be
                    if err<best_err:
                        best_err=err; best_e0=e0; best_e1=e1
            e0=best_e0; e1=best_e1
            # build palette
            r0,g0,b0=_565_to_rgb(e0); r1,g1,b1=_565_to_rgb(e1)
            if e0>e1:
                c2=((2*int(r0)+int(r1))//3,(2*int(g0)+int(g1))//3,(2*int(b0)+int(b1))//3)
                c3=((int(r0)+2*int(r1))//3,(int(g0)+2*int(g1))//3,(int(b0)+2*int(b1))//3)
                palette=[(r0,g0,b0),(r1,g1,b1),c2,c3]
            else:
                c2=((int(r0)+int(r1))//2,(int(g0)+int(g1))//2,(int(b0)+int(b1))//2)
                palette=[(r0,g0,b0),(r1,g1,b1),c2,(0,0,0)]
            # indices
            indices=0
            idxlist=[]
            for p in pixels:
                # find nearest
                best=0; bestd=1e9
                for k,c in enumerate(palette):
                    d=int(p[0]-c[0])**2+int(p[1]-c[1])**2+int(p[2]-c[2])**2
                    if d<bestd: bestd=d; best=k
                idxlist.append(best)
            # pack indices: 4 bytes, 2 bits each, row-major, low bits first texel
            idx_bytes=bytearray(4)
            for i,idx in enumerate(idxlist):
                bytepos=i//4; bitpos=(i%4)*2
                idx_bytes[bytepos] |= (idx & 3) << bitpos
            block=struct.pack('<HH', e0, e1)+bytes(idx_bytes)
            blocks.append(block)
    return b''.join(blocks), ph, pw

def decode_bc1(data, h, w):
    ph=_pad_dim(h); pw=_pad_dim(w)
    nblocks=(ph//4)*(pw//4)
    assert len(data)>=nblocks*8
    out=np.zeros((ph,pw,3),dtype=np.uint8)
    off=0
    for by in range(0,ph,4):
        for bx in range(0,pw,4):
            e0,e1=struct.unpack('<HH', data[off:off+4]); off+=4
            idx_bytes=data[off:off+4]; off+=4
            idxlist=[]
            for i in range(16):
                bytepos=i//4; bitpos=(i%4)*2
                idxlist.append((idx_bytes[bytepos]>>bitpos)&3)
            r0,g0,b0=_565_to_rgb(e0); r1,g1,b1=_565_to_rgb(e1)
            if e0>e1:
                c2=((2*int(r0)+int(r1))//3,(2*int(g0)+int(g1))//3,(2*int(b0)+int(b1))//3)
                c3=((int(r0)+2*int(r1))//3,(int(g0)+2*int(g1))//3,(int(b0)+2*int(b1))//3)
                palette=[(r0,g0,b0),(r1,g1,b1),c2,c3]
            else:
                c2=((int(r0)+int(r1))//2,(int(g0)+int(g1))//2,(int(b0)+int(b1))//2)
                palette=[(r0,g0,b0),(r1,g1,b1),c2,(0,0,0)]
            for i in range(16):
                y,x=divmod(i,4)
                c=palette[idxlist[i]]
                out[by+y,bx+x]=c
    return out[:h,:w]

def psnr(orig, recon):
    mse=np.mean((orig.astype(float)-recon.astype(float))**2)
    if mse==0: return float('inf')
    return 10*np.log10(255.0**2/mse)

if __name__=='__main__':
    # test
    import random
    random.seed(1)
    for (h,w) in [(1,1),(3,5),(4,4),(7,9),(64,64)]:
        img=np.random.randint(0,256,(h,w,3),dtype=np.uint8)
        data,ph,pw=encode_bc1(img)
        assert len(data)==(ph//4)*(pw//4)*8
        recon=decode_bc1(data,h,w)
        p=psnr(img,recon)
        print(f'{h}x{w}: encoded {len(data)} bytes, PSNR={p:.2f}dB')
    # uniform color
    img=np.full((8,8,3),[255,0,0],dtype=np.uint8)
    data,ph,pw=encode_bc1(img)
    recon=decode_bc1(data,8,8)
    print('uniform red PSNR:', psnr(img,recon))
    # gradient
    g=np.zeros((16,16,3),dtype=np.uint8)
    for y in range(16):
        for x in range(16):
            g[y,x]=[x*16,y*16,128]
    data,ph,pw=encode_bc1(g)
    recon=decode_bc1(data,16,16)
    print('gradient PSNR:', psnr(g,recon))
