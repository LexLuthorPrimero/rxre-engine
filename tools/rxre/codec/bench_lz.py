import os, subprocess, time, statistics, json
ZSTD='/usr/bin/zstd'
RLE='/home/lucas/Escritorio/rxre/tools/rxre/codec/rx550_codec'
def make_data(kind, n):
    if kind=='uniform': return bytes([42])*n
    if kind=='repeated': return (b'ABCD'*(n//4))[:n]
    if kind=='random': return os.urandom(n)
    if kind=='image': return bytes((i%256 for i in range(n)))
    if kind=='text': return (b'hello world '*(n//12))[:n]
    return os.urandom(n)

sizes=[4*1024,64*1024,1024*1024]
kinds=['uniform','repeated','random','image','text']
results=[]
for kind in kinds:
    for sz in sizes:
        data=make_data(kind,sz)
        open('/tmp/bench_in.bin','wb').write(data)
        # RLE
        subprocess.run([RLE,'c','/tmp/bench_in.bin','/tmp/rle.rle'],check=True,stderr=subprocess.DEVNULL)
        rle_size=os.path.getsize('/tmp/rle.rle')
        # zstd
        subprocess.run([ZSTD,'-q','-f','-o','/tmp/zstd.zst','/tmp/bench_in.bin'],check=True,stderr=subprocess.DEVNULL)
        zstd_size=os.path.getsize('/tmp/zstd.zst')
        # roundtrip zstd
        subprocess.run([ZSTD,'-q','-d','-f','-o','/tmp/zstd.out','/tmp/zstd.zst'],check=True,stderr=subprocess.DEVNULL)
        assert open('/tmp/zstd.out','rb').read()==data
        results.append({
            'kind':kind,'size':sz,
            'rle_ratio':round(rle_size/sz,4),
            'zstd_ratio':round(zstd_size/sz,4),
            'rle_size':rle_size,'zstd_size':zstd_size,
        })
json.dump(results,open('/tmp/bench_lz_results.json','w'),indent=2)
for r in results:
    print(f"{r['kind']:8s} {r['size']:>10} RLE={r['rle_ratio']:.4f} zstd={r['zstd_ratio']:.4f}")
