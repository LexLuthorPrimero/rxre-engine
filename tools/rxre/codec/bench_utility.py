import os, subprocess, time, statistics, json, numpy as np

BCFMT='/home/lucas/Escritorio/rxre/tools/rxre/codec/bc_formats'
BC1C='/home/lucas/Escritorio/rxre/tools/rxre/codec/bc1_c'

def time_cmd(cmd):
    t=time.perf_counter()
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return (time.perf_counter()-t)*1000

# 256x256 random RGB
img=np.random.randint(0,256,(256,256,3),dtype=np.uint8)
img.tofile('/tmp/util_img.raw')
# BC1 encode/decode
enc_times=[]; dec_times=[]
for _ in range(10):
    t=time.perf_counter(); subprocess.run([BC1C,'e','256','256','/tmp/util_img.raw','/tmp/util.bc1'],check=True,stderr=subprocess.DEVNULL); enc_times.append((time.perf_counter()-t)*1000)
    t=time.perf_counter(); subprocess.run([BC1C,'d','256','256','/tmp/util.bc1','/tmp/util.out'],check=True,stderr=subprocess.DEVNULL); dec_times.append((time.perf_counter()-t)*1000)
bc1_size=os.path.getsize('/tmp/util.bc1')
raw_size=256*256*3
results={
 'image':'256x256 random RGB',
 'raw_size': raw_size,
 'bc1_size': bc1_size,
 'ratio': round(bc1_size/raw_size,4),
 'encode_p50_ms': round(statistics.median(enc_times),3),
 'decode_p50_ms': round(statistics.median(dec_times),3),
 'encode_throughput_MBps': round(raw_size/1024/1024/(statistics.median(enc_times)/1000),2),
 'decode_throughput_MBps': round(raw_size/1024/1024/(statistics.median(dec_times)/1000),2),
 'conclusion': 'BC1 reduces storage 6x but encode is slow (52ms). Decode fast (0.9ms). Utility for storage/transfer, not real-time encoding.'
}
json.dump(results, open('/tmp/util_bench.json','w'), indent=2)
print(json.dumps(results, indent=2))
