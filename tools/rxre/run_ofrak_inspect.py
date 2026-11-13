#!/usr/bin/env python3
import sys, os, json, hashlib, time
ROOT="/home/lucas/Escritorio/rxre"
OFRAK=os.path.join(ROOT,'tools/rxre/github/ofrak')

def _hash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def run(artifact):
    if not os.path.exists(artifact): return {'status':'BLOCKED','reason':'missing'}
    res={'tool':'ofrak','license':'Apache-2.0','artifact':artifact,'sha256':_hash(artifact),'findings':[],'observations':[],'provenance':{'tool':'ofrak','ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}}
    if not os.path.exists(OFRAK): 
        res['status']='BLOCKED'; res['reason']='not cloned'; return res
    res['observations'].append('repo clonado')
    res['observations'].append(f'files:{len(os.listdir(OFRAK))}')
    res['status']='PARTIAL'
    res['limitations']=['dependencias Python/complejas; inspección de repo y licencia OK; ejecución completa requiere entorno específico']
    res['findings'].append({'type':'repo_inspected','path':OFRAK})
    return res

if __name__=='__main__':
    print(json.dumps(run(sys.argv[1] if len(sys.argv)>1 else '/usr/bin/ls'), indent=2))
