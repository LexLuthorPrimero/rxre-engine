#!/usr/bin/env python3
import sys, os, json, hashlib, time, tempfile, shutil
ROOT="/home/lucas/Escritorio/rxre"
OFRAK=os.path.join(ROOT,'tools/rxre/github/ofrak')

def _hash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def run(artifact, allow=False):
    if not os.path.exists(artifact): return {'status':'BLOCKED','reason':'missing'}
    res={'tool':'ofrak','license':'Apache-2.0','artifact':artifact,'sha256_baseline':_hash(artifact),'phase':'transform_test','provenance':{'tool':'ofrak','ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}}
    if not os.path.exists(OFRAK): 
        res['status']='BLOCKED'; res['reason']='not cloned'; return res
    if not allow:
        res['status']='BLOCKED'; res['reason']='allow=False (sin autorización operativa)'; return res
    # prueba aislada
    WORK=tempfile.mkdtemp(prefix='m343_ofrak_',dir='/tmp')
    copy_path=os.path.join(WORK,os.path.basename(artifact)+'.copy')
    shutil.copy2(artifact,copy_path)
    h0=_hash(copy_path)
    try:
        with open(copy_path,'rb') as f:
            data=f.read()
        if data[:4]==b'\x7fELF':
            shutil.rmtree(WORK)
            res['status']='BLOCKED'; res['reason']='binario no modificado (transformación mínima no aplicable sin análisis específico)'; res['h0']=h0
            return res
        # texto: no hacer cambio destructivo
        shutil.rmtree(WORK)
        res['status']='NOT_EXECUTED'; res['reason']='sin cambio seguro aplicable'; res['h0']=h0
        return res
    except Exception as e:
        try: shutil.rmtree(WORK)
        except: pass
        res['status']='BLOCKED'; res['reason']=str(e)
        return res

if __name__=='__main__':
    print(json.dumps(run(sys.argv[1] if len(sys.argv)>1 else '/usr/bin/ls', allow=False), indent=2))
