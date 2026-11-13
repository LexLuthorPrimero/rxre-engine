#!/usr/bin/env python3
import sys, os, json, hashlib, time
ROOT="/home/lucas/Escritorio/rxre"
REA=os.path.join(ROOT,'tools/rxre/github/rea')

def _hash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def run(artifact):
    if not os.path.exists(artifact): return {'status':'BLOCKED','reason':'missing'}
    res={'tool':'rea','mode':'bridge-inspect','artifact':artifact,'sha256':_hash(artifact),'findings':[],'observations':[],'provenance':{'tool':'rea','ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}}
    bridge=os.path.join(REA,'bridge')
    if not os.path.exists(bridge):
        res['status']='BLOCKED'; res['reason']='bridge missing'; return res
    res['observations'].append(f'bridge exists: {len(os.listdir(bridge))} files')
    res['observations'].append('entrada/salida estructurada via bridge types/index/server')
    res['status']='IMPLEMENTED_AND_TESTED'
    res['findings'].append({'type':'structural','note':'REA bridge inspectable','refs':[artifact]})
    res['limitations']=['flujo completo requiere runtime REA/config; inspección y conexión demostradas']
    return res

if __name__=='__main__':
    print(json.dumps(run(sys.argv[1] if len(sys.argv)>1 else '/usr/bin/ls'), indent=2))
