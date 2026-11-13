#!/usr/bin/env python3
"""BC4 (single channel) and BC5 (two channels) block compression."""
import struct, numpy as np
from bc1 import encode_bc1, decode_bc1

def _pad(n): return ((n+3)//4)*4

def encode_bc4(channel):
    # channel: 2D uint8 array
    h,w = channel.shape
    ph=_pad(h); pw=_pad(w)
    padded=np.zeros((ph,pw),dtype=np.uint8)
    padded[:h,:w]=channel
    blocks=[]
    for by in range(0,ph,4):
        for bx in range(0,pw,4):
            block=padded[by:by+4,bx:bx+4].flatten()
            # endpoints: min and max
            mn=int(block.min()); mx=int(block.max())
            if mn==mx:
                # all same
                out=struct.pack('<BB', mx, mn)+b'\x00'*6
                blocks.append(out); continue
            # quantize endpoints to 8-bit (already)
            e0=mx; e1=mn
            if e0<e1: e0,e1=e1,e0
            # 6 interpolated values (8 total)
            # palette: if e0>e1: 6 intermediate; else 4 intermediate + transparent
            if e0>e1:
                pal=[e0, e1,
                     (6*e0+1*e1)//7, (5*e0+2*e1)//7, (4*e0+3*e1)//7,
                     (3*e0+4*e1)//7, (2*e0+5*e1)//7, (1*e0+6*e1)//7]
            else:
                pal=[e0, e1,
                     (4*e0+1*e1)//5, (3*e0+2*e1)//5, (2*e0+3*e1)//5, (1*e0+4*e1)//5,
                     0, 255]
            # indices: 3 bits each (16*3=48 bits = 6 bytes)
            idx_bytes=bytearray(6)
            for i,val in enumerate(block):
                be=1e9; best=0
                for k,c in enumerate(pal):
                    d=abs(int(val)-c)
                    if d<be: be=d; best=k
                # pack 3 bits
                bitpos=i*3
                bytepos=bitpos//8; bitoff=bitpos%8
                # write up to 2 bytes
                code=best & 0x7
                idx_bytes[bytepos] |= (code << bitoff) & 0xFF
                if bitoff+3>8:
                    idx_bytes[bytepos+1] |= (code >> (8-bitoff)) & 0xFF
            blockout=struct.pack('<BB', e0, e1)+bytes(idx_bytes)
            blocks.append(blockout)
    return b''.join(blocks), ph, pw

def decode_bc4(data, h, w):
    ph=_pad(h); pw=_pad(w)
    out=np.zeros((ph,pw),dtype=np.uint8)
    off=0
    for by in range(0,ph,4):
        for bx in range(0,pw,4):
            e0=data[off]; e1=data[off+1]; off+=2
            idx_bytes=data[off:off+6]; off+=6
            if e0>e1:
                pal=[e0, e1,
                     (6*e0+1*e1)//7, (5*e0+2*e1)//7, (4*e0+3*e1)//7,
                     (3*e0+4*e1)//7, (2*e0+5*e1)//7, (1*e0+6*e1)//7]
            else:
                pal=[e0, e1,
                     (4*e0+1*e1)//5, (3*e0+2*e1)//5, (2*e0+3*e1)//5, (1*e0+4*e1)//5,
                     0, 255]
            for i in range(16):
                bitpos=i*3
                bytepos=bitpos//8; bitoff=bitpos%8
                code=(idx_bytes[bytepos]>>(bitoff)) & 0x7
                if bitoff+3>8:
                    code |= (idx_bytes[bytepos+1] << (8-bitoff)) & 0x7
                y,x=divmod(i,4)
                out[by+y,bx+x]=pal[code]
    return out[:h,:w]

def encode_bc5(ch0, ch1):
    d0,ph,pw=encode_bc4(ch0)
    d1,_,_=encode_bc4(ch1)
    # interleave: BC5 is two BC4 blocks (first channel then second) in 16 bytes per 4x4? Actually BC5 = 2 BC4 blocks concatenated per 4x4 block (16 bytes total: 8+8)
    # Our encode_bc4 returns all blocks concatenated. Need to interleave per block.
    nblocks=(ph//4)*(pw//4)
    out=bytearray()
    for i in range(nblocks):
        out += d0[i*8:(i+1)*8]
        out += d1[i*8:(i+1)*8]
    return bytes(out), ph, pw

def decode_bc5(data, h, w):
    ph=_pad(h); pw=_pad(w)
    nblocks=(ph//4)*(pw//4)
    ch0=np.zeros((ph,pw),dtype=np.uint8)
    ch1=np.zeros((ph,pw),dtype=np.uint8)
    off=0
    for by in range(0,ph,4):
        for bx in range(0,pw,4):
            block0=data[off:off+8]; off+=8
            block1=data[off:off+8]; off+=8
            # decode each 4x4
            e0=block0[0]; e1=block0[1]
            # reuse decode logic per block
            # (simplified: decode into temp 4x4)
            tmp0=decode_bc4(block0,4,4)
            tmp1=decode_bc4(block1,4,4)
            ch0[by:by+4,bx:bx+4]=tmp0
            ch1[by:by+4,bx:bx+4]=tmp1
    return ch0[:h,:w], ch1[:h,:w]

def encode_bc3(rgba):
    # alpha: BC4-style 8-bit endpoints + 6 bytes indices (8 bytes)
    # color: BC1-style (8 bytes)
    h,w=rgba.shape[:2]
    rgb=rgba[:,:,:3]
    alpha=rgba[:,:,3]
    # encode color with BC1
    from bc1 import encode_bc1, decode_bc1
    color_data,ph,pw=encode_bc1(rgb)
    # encode alpha with BC4
    alpha_data,_,_=encode_bc4(alpha)
    # interleave: BC3 = 8 bytes alpha + 8 bytes color per 4x4 block
    nblocks=(ph//4)*(pw//4)
    out=bytearray()
    for i in range(nblocks):
        out += alpha_data[i*8:(i+1)*8]
        out += color_data[i*8:(i+1)*8]
    return bytes(out), ph, pw

def decode_bc3(data, h, w):
    ph=_pad(h); pw=_pad(w)
    nblocks=(ph//4)*(pw//4)
    rgb=np.zeros((ph,pw,3),dtype=np.uint8)
    alpha=np.zeros((ph,pw),dtype=np.uint8)
    off=0
    for by in range(0,ph,4):
        for bx in range(0,pw,4):
            ablock=data[off:off+8]; off+=8
            cblock=data[off:off+8]; off+=8
            a=decode_bc4(ablock,4,4)
            c=decode_bc1(cblock,4,4)
            alpha[by:by+4,bx:bx+4]=a
            rgb[by:by+4,bx:bx+4]=c
    return rgb[:h,:w], alpha[:h,:w]

if __name__=='__main__':
    # tests
    for (h,w) in [(1,1),(4,4),(7,9),(64,64)]:
        ch=np.random.randint(0,256,(h,w),dtype=np.uint8)
        d,ph,pw=encode_bc4(ch)
        assert len(d)==(ph//4)*(pw//4)*8
        r=decode_bc4(d,h,w)
        mse=np.mean((ch.astype(float)-r.astype(float))**2)
        print(f'BC4 {h}x{w}: {len(d)} bytes, MSE={mse:.2f}')
    # BC5
    ch0=np.random.randint(0,256,(4,4),dtype=np.uint8)
    ch1=np.random.randint(0,256,(4,4),dtype=np.uint8)
    d,ph,pw=encode_bc5(ch0,ch1)
    assert len(d)==(ph//4)*(pw//4)*16
    r0,r1=decode_bc5(d,4,4)
    print(f'BC5 4x4: {len(d)} bytes, ch0 MSE={np.mean((ch0.astype(float)-r0.astype(float))**2):.2f}')
    # BC3
    rgba=np.random.randint(0,256,(4,4,4),dtype=np.uint8)
    d,ph,pw=encode_bc3(rgba)
    assert len(d)==(ph//4)*(pw//4)*16
    rgb,a=decode_bc3(d,4,4)
    print(f'BC3 4x4: {len(d)} bytes')
    print('ALL TESTS PASSED')
