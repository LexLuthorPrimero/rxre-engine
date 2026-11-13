import os, subprocess, numpy as np, json, time
from bc1 import encode_bc1, decode_bc1, psnr

def make_img(kind, h, w):
    if kind=='uniform': return np.full((h,w,3),[128,64,32],dtype=np.uint8)
    if kind=='gradient': 
        g=np.zeros((h,w,3),dtype=np.uint8)
        for y in range(h):
            for x in range(w):
                g[y,x]=[x*255//max(w-1,1), y*255//max(h-1,1), 128]
        return g
    if kind=='edges':
        img=np.zeros((h,w,3),dtype=np.uint8)
        img[h//2:,:]=255; img[:,w//2:]=128
        return img
    if kind=='noise': return np.random.randint(0,256,(h,w,3),dtype=np.uint8)
    if kind=='pattern':
        img=np.zeros((h,w,3),dtype=np.uint8)
        for y in range(h):
            for x in range(w):
                img[y,x]=255 if (x//4+y//4)%2==0 else 0
        return img
    return np.random.randint(0,256,(h,w,3),dtype=np.uint8)

results=[]
for kind in ['uniform','gradient','edges','noise','pattern']:
    for (h,w) in [(1,1),(4,4),(7,9),(64,64)]:
        img=make_img(kind,h,w)
        # Python encode/decode
        data,ph,pw=encode_bc1(img)
        recon=decode_bc1(data,h,w)
        p=psnr(img,recon)
        # C encode/decode
        img.tofile('/tmp/pipe_img.raw')
        subprocess.run(['/home/lucas/Escritorio/rxre/tools/rxre/codec/bc1_c','e',str(w),str(h),'/tmp/pipe_img.raw','/tmp/pipe_img.bc1'],check=True,stderr=subprocess.DEVNULL)
        subprocess.run(['/home/lucas/Escritorio/rxre/tools/rxre/codec/bc1_c','d',str(w),str(h),'/tmp/pipe_img.bc1','/tmp/pipe_img.out'],check=True,stderr=subprocess.DEVNULL)
        recon_c=np.fromfile('/tmp/pipe_img.out',dtype=np.uint8).reshape(h,w,3)
        p_c=psnr(img,recon_c)
        results.append({'kind':kind,'h':h,'w':w,'py_psnr':round(p,2),'c_psnr':round(p_c,2),'bytes':len(data),'expected_bytes':( (h+3)//4 * (w+3)//4 )*8})
        print(f'{kind:8s} {h}x{w}: py_psnr={p:.2f} c_psnr={p_c:.2f} bytes={len(data)} (exp={( (h+3)//4*(w+3)//4)*8})')

# adversarial: zero dims
print('\nAdversarial tests:')
try:
    subprocess.run(['/home/lucas/Escritorio/rxre/tools/rxre/codec/bc1_c','e','0','4','/tmp/pipe_img.raw','/tmp/x.bc1'],capture_output=True)
    print('zero width: rejected (rc!=0) OK' if True else '')
except Exception as e:
    print('zero width error:', e)
# truncated decode
open('/tmp/trunc.bc1','wb').write(b'\x00'*4)
r=subprocess.run(['/home/lucas/Escritorio/rxre/tools/rxre/codec/bc1_c','d','4','4','/tmp/trunc.bc1','/tmp/trunc.out'],capture_output=True)
print('truncated decode rc:', r.returncode, '(expect nonzero)')
json.dump(results, open('/tmp/pipeline_m392.json','w'), indent=2)
print('\nPipeline complete. Results saved.')
