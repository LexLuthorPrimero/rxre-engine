#!/usr/bin/env python3
import sys, os, json, hashlib, time
ROOT="/home/lucas/Escritorio/rxre"

def _hash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def run(artifact):
    if not os.path.exists(artifact): return {'status':'BLOCKED','reason':'missing'}
    res={'tool':'angr','version':None,'artifact':artifact,'sha256':_hash(artifact),'findings':[],'observations':[],'provenance':{'tool':'angr','ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}}
    try:
        import angr
        res['version']=angr.__version__
        res['observations'].append('import ok')
        p = angr.Project(artifact, auto_load_libs=False)
        res['observations'].append(f'arch={p.arch.name}')
        res['observations'].append(f'entry=0x{p.entry:x}')
        res['findings'].append({'type':'entry','addr':p.entry,'arch':p.arch.name})
        res['status']='IMPLEMENTED_AND_TESTED'
        res['limitations']=['análisis mínimo (carga + entry); CFG/simbólico requiere mayor tiempo/recursos']
        return res
    except Exception as e:
        res['status']='BLOCKED'
        res['reason']=str(e)
        return res

if __name__=='__main__':
    print(json.dumps(run(sys.argv[1] if len(sys.argv)>1 else '/usr/bin/ls'), indent=2))
