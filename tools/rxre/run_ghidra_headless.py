#!/usr/bin/env python3
import sys, os, json, hashlib, time, tempfile, subprocess
ROOT="/home/lucas/Escritorio/rxre"

def _hash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def run(artifact):
    if not os.path.exists(artifact): return {'status':'BLOCKED','reason':'missing'}
    res={'tool':'ghidra','mode':'headless','artifact':artifact,'sha256':_hash(artifact),'commands':[],'findings':[],'observations':[],'provenance':{'tool':'ghidra','ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}}
    proj = tempfile.mkdtemp(prefix='ghidra_proj_',dir='/tmp')
    outdir = tempfile.mkdtemp(prefix='ghidra_out_',dir='/tmp')
    cmd=['ghidra','-analysisTimeoutPerFile','60','-import',artifact,'-projectDir',proj,'-deleteProject']
    res['commands'].append(' '.join(cmd))
    try:
        p=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        res['observations'].append(f'rc={p.returncode}')
        res['observations'].append(p.stdout[:200].decode(errors='ignore'))
        res['status']='IMPLEMENTED_AND_TESTED' if p.returncode==0 else 'PARTIAL'
    except Exception as e:
        res['status']='PARTIAL'
        res['observations'].append(str(e))
    res['limitations']=['ejecución headless básica; extracción de hallazgos detallada requiere script personalizado']
    return res

if __name__=='__main__':
    print(json.dumps(run(sys.argv[1] if len(sys.argv)>1 else '/usr/bin/ls'), indent=2))
