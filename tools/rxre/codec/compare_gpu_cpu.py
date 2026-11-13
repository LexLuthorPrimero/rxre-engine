import os, subprocess, numpy as np, json, time

def run(fmt, w, h, raw_path):
    # encode with C
    subprocess.run(['/home/lucas/Escritorio/rxre/tools/rxre/codec/bc_formats','e',fmt.replace('bc1','bc1').replace('bc1a','bc1'),str(w),str(h),raw_path,f'/tmp/{fmt}_{w}x{h}.bin'],check=True,stderr=subprocess.DEVNULL)
    # Actually bc_formats uses 'bc1' for color. Let's use bc1.
    # decode CPU
    subprocess.run(['/home/lucas/Escritorio/rxre/tools/rxre/codec/bc_formats','d',fmt if fmt!='bc1a' else 'bc1',str(w),str(h),f'/tmp/{fmt}_{w}x{h}.bin',f'/tmp/{fmt}_{w}x{h}_cpu.out'],check=True,stderr=subprocess.DEVNULL)
    # GPU sample
    subprocess.run(['/home/lucas/Escritorio/rxre/tools/rxre/codec/vk_bc_multi',fmt if fmt!='bc1a' else 'bc1',str(w),str(h),f'/tmp/{fmt}_{w}x{h}.bin'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    # read GPU output
    gpu=np.fromfile('/tmp/gpu_out.bin',dtype=np.float32).reshape(h,w,4)
    # CPU decode
    if fmt=='bc4':
        cpu=np.fromfile(f'/tmp/{fmt}_{w}x{h}_cpu.out',dtype=np.uint8).reshape(h,w)
        cpu_f=cpu.astype(np.float32)/255.0
        gpu_ch=gpu[:,:,0]
        maxerr=np.max(np.abs(gpu_ch-cpu_f))
        meanerr=np.mean(np.abs(gpu_ch-cpu_f))
    elif fmt=='bc1':
        cpu=np.fromfile(f'/tmp/{fmt}_{w}x{h}_cpu.out',dtype=np.uint8).reshape(h,w,3)
        cpu_f=cpu.astype(np.float32)/255.0
        gpu_rgb=gpu[:,:,:3]
        maxerr=np.max(np.abs(gpu_rgb-cpu_f))
        meanerr=np.mean(np.abs(gpu_rgb-cpu_f))
    else:
        cpu=np.fromfile(f'/tmp/{fmt}_{w}x{h}_cpu.out',dtype=np.uint8)
        # unknown
        maxerr=0; meanerr=0
    print(f'{fmt} {w}x{h}: max_err={maxerr:.6f} mean_err={meanerr:.6f}')
    return maxerr, meanerr

# Test BC1
img_data=__import__('numpy').random.randint(0,256,(8,8,3),dtype=__import__('numpy').uint8)
img_data.tofile('/tmp/bc1_8x8.raw')
# encode with bc1_c
subprocess.run(['/home/lucas/Escritorio/rxre/tools/rxre/codec/bc1_c','e','8','8','/tmp/bc1_8x8.raw','/tmp/bc1_8x8.bin'],check=True,stderr=subprocess.DEVNULL)
# copy to expected path
# run comparison manually
subprocess.run(['/home/lucas/Escritorio/rxre/tools/rxre/codec/vk_bc_multi','bc1','8','8','/tmp/bc1_8x8.bin'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
gpu=np.fromfile('/tmp/gpu_out.bin',dtype=np.float32).reshape(8,8,4)
# CPU decode
subprocess.run(['/home/lucas/Escritorio/rxre/tools/rxre/codec/bc1_c','d','8','8','/tmp/bc1_8x8.bin','/tmp/bc1_8x8_cpu.out'],check=True,stderr=subprocess.DEVNULL)
cpu=np.fromfile('/tmp/bc1_8x8_cpu.out',dtype=np.uint8).reshape(8,8,3)
cpu_f=cpu.astype(np.float32)/255.0
maxerr=np.max(np.abs(gpu[:,:,:3]-cpu_f))
meanerr=np.mean(np.abs(gpu[:,:,:3]-cpu_f))
print(f'BC1 8x8: max_err={maxerr:.6f} mean_err={meanerr:.6f} (expect ~0 for nearest)')

# BC4
ch=np.random.randint(0,256,(8,8),dtype=np.uint8)
ch.tofile('/tmp/bc4_8x8.raw')
subprocess.run(['/home/lucas/Escritorio/rxre/tools/rxre/codec/bc_formats','e','bc4','8','8','/tmp/bc4_8x8.raw','/tmp/bc4_8x8.bin'],check=True,stderr=subprocess.DEVNULL)
subprocess.run(['/home/lucas/Escritorio/rxre/tools/rxre/codec/vk_bc_multi','bc4','8','8','/tmp/bc4_8x8.bin'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
gpu=np.fromfile('/tmp/gpu_out.bin',dtype=np.float32).reshape(8,8,4)
subprocess.run(['/home/lucas/Escritorio/rxre/tools/rxre/codec/bc_formats','d','bc4','8','8','/tmp/bc4_8x8.bin','/tmp/bc4_8x8_cpu.out'],check=True,stderr=subprocess.DEVNULL)
cpu=np.fromfile('/tmp/bc4_8x8_cpu.out',dtype=np.uint8).reshape(8,8)
cpu_f=cpu.astype(np.float32)/255.0
maxerr=np.max(np.abs(gpu[:,:,0]-cpu_f))
meanerr=np.mean(np.abs(gpu[:,:,0]-cpu_f))
print(f'BC4 8x8: max_err={maxerr:.6f} mean_err={meanerr:.6f}')
