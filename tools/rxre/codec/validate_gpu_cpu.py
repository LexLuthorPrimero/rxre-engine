import os, subprocess, numpy as np, json

BC1C='/home/lucas/Escritorio/rxre/tools/rxre/codec/bc1_c'
BCFMT='/home/lucas/Escritorio/rxre/tools/rxre/codec/bc_formats'
VKMULTI='/home/lucas/Escritorio/rxre/tools/rxre/codec/vk_bc_multi'
results=[]

# BC1 test
w,h=8,8
img=np.random.randint(0,256,(h,w,3),dtype=np.uint8)
img.tofile('/tmp/bc1_8x8.raw')
subprocess.run([BC1C,'e',str(w),str(h),'/tmp/bc1_8x8.raw','/tmp/bc1_8x8.bin'],check=True,stderr=subprocess.DEVNULL)
subprocess.run([BC1C,'d',str(w),str(h),'/tmp/bc1_8x8.bin','/tmp/bc1_8x8_cpu.out'],check=True,stderr=subprocess.DEVNULL)
subprocess.run([VKMULTI,'bc1',str(w),str(h),'/tmp/bc1_8x8.bin'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
gpu=np.fromfile('/tmp/gpu_out.bin',dtype=np.float32).reshape(h,w,4)
cpu=np.fromfile('/tmp/bc1_8x8_cpu.out',dtype=np.uint8).reshape(h,w,3)
cpu_f=cpu.astype(np.float32)/255.0
maxerr=float(np.max(np.abs(gpu[:,:,:3]-cpu_f)))
meanerr=float(np.mean(np.abs(gpu[:,:,:3]-cpu_f)))
results.append({'format':'BC1','w':w,'h':h,'max_err':round(maxerr,6),'mean_err':round(meanerr,6)})
print(f'BC1 {w}x{h}: max_err={maxerr:.6f} mean_err={meanerr:.6f}')

# BC4 test
ch=np.random.randint(0,256,(8,8),dtype=np.uint8)
ch.tofile('/tmp/bc4_8x8.raw')
subprocess.run([BCFMT,'e','bc4',str(w),str(h),'/tmp/bc4_8x8.raw','/tmp/bc4_8x8.bin'],check=True,stderr=subprocess.DEVNULL)
subprocess.run([BCFMT,'d','bc4',str(w),str(h),'/tmp/bc4_8x8.bin','/tmp/bc4_8x8_cpu.out'],check=True,stderr=subprocess.DEVNULL)
subprocess.run([VKMULTI,'bc4',str(w),str(h),'/tmp/bc4_8x8.bin'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
gpu=np.fromfile('/tmp/gpu_out.bin',dtype=np.float32).reshape(h,w,4)
cpu=np.fromfile('/tmp/bc4_8x8_cpu.out',dtype=np.uint8).reshape(h,w)
cpu_f=cpu.astype(np.float32)/255.0
maxerr=float(np.max(np.abs(gpu[:,:,0]-cpu_f)))
meanerr=float(np.mean(np.abs(gpu[:,:,0]-cpu_f)))
results.append({'format':'BC4','w':w,'h':h,'max_err':round(maxerr,6),'mean_err':round(meanerr,6)})
print(f'BC4 {w}x{h}: max_err={maxerr:.6f} mean_err={meanerr:.6f}')

json.dump(results, open('/tmp/gpu_cpu_validation.json','w'), indent=2)
print('Validation complete.')
