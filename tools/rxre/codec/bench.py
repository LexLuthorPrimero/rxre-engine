import os, subprocess, time, random, statistics, json
CODEC='/home/lucas/Escritorio/rxre/tools/rxre/codec/rx550_codec'
def make_data(kind, n):
    if kind=='uniform': return bytes([42])*n
    if kind=='repeated': return (b'ABCD'* (n//4))[:n]
    if kind=='random': return os.urandom(n)
    if kind=='image': 
        # synthetic image: gradient + noise
        import struct
        return bytes((i%256 for i in range(n)))
    return os.urandom(n)

sizes=[4*1024,64*1024,1024*1024,16*1024*1024]
kinds=['uniform','repeated','random','image']
results=[]
for kind in kinds:
    for sz in sizes:
        data=make_data(kind,sz)
        open('/tmp/bench_in.bin','wb').write(data)
        # warmup
        subprocess.run([CODEC,'c','/tmp/bench_in.bin','/tmp/bench_out.rle'],check=True,stderr=subprocess.DEVNULL)
        subprocess.run([CODEC,'d','/tmp/bench_out.rle','/tmp/bench_out.bin'],check=True,stderr=subprocess.DEVNULL)
        # measure compress
        ct=[]; dt=[]; cr=None
        for _ in range(10):
            t=time.perf_counter()
            subprocess.run([CODEC,'c','/tmp/bench_in.bin','/tmp/bench_out.rle'],check=True,stderr=subprocess.DEVNULL)
            ct.append((time.perf_counter()-t)*1000)
            t=time.perf_counter()
            subprocess.run([CODEC,'d','/tmp/bench_out.rle','/tmp/bench_out.bin'],check=True,stderr=subprocess.DEVNULL)
            dt.append((time.perf_counter()-t)*1000)
        # verify roundtrip
        assert open('/tmp/bench_out.bin','rb').read()==data
        cr=os.path.getsize('/tmp/bench_out.rle')
        results.append({
            'kind':kind,'size':sz,
            'orig':sz,'compressed':cr,
            'ratio':round(cr/sz,4),
            'compress_p50_ms':round(statistics.median(ct),3),
            'compress_p95_ms':round(sorted(ct)[int(0.95*len(ct))-1],3),
            'decompress_p50_ms':round(statistics.median(dt),3),
            'decompress_p95_ms':round(sorted(dt)[int(0.95*len(dt))-1],3),
            'compress_throughput_MBps':round(sz/1024/1024/(statistics.median(ct)/1000),2),
            'decompress_throughput_MBps':round(sz/1024/1024/(statistics.median(dt)/1000),2),
            'roundtrip':'PASS'
        })
json.dump(results,open('/tmp/bench_results.json','w'),indent=2)
for r in results:
    print(f"{r['kind']:8s} {r['size']:>10} -> {r['compressed']:>10} ratio={r['ratio']:.4f} c_p50={r['compress_p50_ms']:.3f}ms d_p50={r['decompress_p50_ms']:.3f}ms")
