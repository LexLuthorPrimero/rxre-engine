#!/usr/bin/env python3
import sys, os, json, hashlib, zlib, struct
ART=sys.argv[1] if len(sys.argv)>1 else '/home/lucas/Escritorio/flash/juego.swf'
data=open(ART,'rb').read()
print('size',len(data))
print('magic',data[:3])
version=data[3]
filelen=struct.unpack('<I',data[4:8])[0]
print('version',version,'filelen',filelen)
if data[:3]==b'CWS':
    body=zlib.decompress(data[8:])
    print('decompressed',len(body))
elif data[:3]==b'FWS':
    body=data[8:]
else:
    body=data[8:]
# parse RECT
def read_rect(buf, off):
    nbits=(buf[off]>>3)
    # total bits
    total=5+nbits*4
    # read bits
    import struct
    # pack into int
    val=0; bitpos=0
    def getbits(n):
        nonlocal val,bitpos
        # ensure enough
        while bitpos < n:
            val = (val<<8)|buf[off+ (bitpos//8)]
            bitpos+=8
        # not exact; use simpler byte approach
        return 0
    # fallback: use bitstring manually
    # read first byte
    b=buf[off]
    nbits=b>>3
    # compute byte length of rect
    import math
    bits=5+4*nbits
    nbytes=(bits+7)//8
    return nbits, nbytes

nbits, nbytes = read_rect(body,0)
print('rect nbits',nbits,'bytes',nbytes)
off=nbytes
# frame rate (8.8 fixed) and frame count
framerate = struct.unpack('>H', body[off:off+2])[0]/256.0
off+=2
framecount = struct.unpack('<H', body[off:off+2])[0]
off+=2
print('framerate',framerate,'framecount',framecount)

# tag parsing
TAG_NAMES={0:'End',1:'ShowFrame',2:'DefineShape',4:'PlaceObject',5:'RemoveObject',6:'DefineBits',7:'DefineButton',8:'JPEGTables',9:'SetBackgroundColor',10:'DefineFont',11:'DefineText',12:'DoAction',13:'DefineFontInfo',14:'DefineSound',15:'StartSound',18:'SoundStreamHead',19:'SoundStreamBlock',20:'DefineBitsLossless',21:'DefineBitsJPEG2',22:'DefineShape2',24:'Protect',26:'PlaceObject2',28:'RemoveObject2',32:'DefineShape3',33:'DefineText2',34:'DefineButton2',35:'DefineBitsJPEG3',36:'DefineBitsLossless2',37:'DefineEditText',39:'DefineSprite',40:'NameCharacter',41:'ProductInfo',43:'FrameLabel',45:'SoundStreamHead2',46:'DefineMorphShape',48:'DefineFont2',56:'ExportAssets',57:'ImportAssets',58:'EnableDebugger',59:'DoInitAction',60:'DefineVideoStream',61:'VideoFrame',62:'DefineFontInfo2',63:'DebugID',64:'EnableDebugger2',65:'ScriptLimits',66:'SetTabIndex',69:'FileAttributes',70:'PlaceObject3',73:'DefineFontAlignZones',74:'CSMTextSettings',75:'DefineFont3',76:'SymbolClass',77:'Metadata',78:'DefineScalingGrid',82:'DoABC',83:'DefineShape4',84:'DefineMorphShape2',86:'DefineSceneAndFrameLabelData',87:'DefineBinaryData',88:'DefineFontName',90:'DefineBitsJPEG4',91:'DefineFont4'}
tags=[]
while off < len(body):
    if off+2>len(body): break
    header=struct.unpack('<H', body[off:off+2])[0]
    off+=2
    code=header>>6
    length=header & 0x3F
    if length==0x3F:
        length=struct.unpack('<I', body[off:off+4])[0]
        off+=4
    tagdata=body[off:off+length]
    off+=length
    tags.append((code,length,tagdata))
    if code==0: break

print('num tags',len(tags))
from collections import Counter
c=Counter(t[0] for t in tags)
for code,n in c.most_common():
    print(code, TAG_NAMES.get(code,'?'), n)

# DoABC tags
doabc=[t for t in tags if t[0]==82]
print('DoABC count',len(doabc))
for idx,t in enumerate(doabc):
    # DoABC: flags(4) + name(null-terminated) + abc data
    flags=struct.unpack('<I',t[2][:4])[0]
    namebytes=t[2][4:]
    ni=namebytes.find(b'\x00')
    name=namebytes[:ni].decode('utf-8','replace') if ni>=0 else ''
    abc=namebytes[ni+1:] if ni>=0 else namebytes
    print(f'  DoABC {idx}: flags={flags} name={name!r} abc_size={len(abc)}')
    # save abc
    outdir='/tmp/swf_extract'
    os.makedirs(outdir,exist_ok=True)
    open(os.path.join(outdir,f'doabc_{idx}.abc'),'wb').write(abc)

# SymbolClass
sym=[t for t in tags if t[0]==76]
print('SymbolClass count',len(sym))
for t in sym:
    # count (2 bytes), then pairs: tag id (2) + name (null-term)
    import struct
    cnt=struct.unpack('<H',t[2][:2])[0]
    off2=2
    for _ in range(cnt):
        tid=struct.unpack('<H',t[2][off2:off2+2])[0]
        off2+=2
        ni=t[2].find(b'\x00',off2)
        nm=t[2][off2:ni].decode('utf-8','replace')
        off2=ni+1
        print('   ',tid,nm)

# Save decompressed body
os.makedirs('/tmp/swf_extract',exist_ok=True)
open('/tmp/swf_extract/body.bin','wb').write(body)
print('body saved')
