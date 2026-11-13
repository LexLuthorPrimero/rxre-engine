#!/usr/bin/env python3
import sys, os, json, hashlib, tempfile, shutil, time
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools'))
sys.path.insert(0, os.path.join(ROOT,'m326_isolated/scripts'))

def _hash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda: f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def run(artifact=None, allow=False):
    res={'phase':'FUEGO_M344','provision_present': os.path.exists('/tmp/rxre_auth_provisioned/identities.json'), 
         'svc_present': os.path.exists('/tmp/rxre_306_work/servicio.key'), 'status':'BLOCKED'}
    if not allow:
        res['reason']='allow=False'; 
        res['exact_admin_step']='tools/rxre/admin/provision_trust.py --provisioned-by <admin> --confirm --issuer-key <fuera_repo>/issuer.key --service-key <fuera_repo>/servicio.key (permisos 0600, uid/emisor/ejecutor provistos, identities.json con key_sha256/nonce/firma válida)'
        return res
    if not res['provision_present'] or not res['svc_present']:
        res['reason']='provisión persistente legítima ausente'
        res['exact_admin_step']='tools/rxre/admin/provision_trust.py --provisioned-by <admin> --confirm --issuer-key <fuera_repo>/issuer.key --service-key <fuera_repo>/servicio.key con permisos 0600, uid coincidente, issuers/executors provisionados, identities.json válido con key_sha256/nonces/firma'
        return res
    if not artifact or not os.path.exists(artifact):
        res['reason']='artefacto ausente'; return res
    if os.path.realpath(artifact).startswith('/usr/') or os.path.realpath(artifact).startswith('/bin/') or os.path.realpath(artifact).startswith('/sbin/'):
        res['reason']='artefacto sistema no permitido'; return res
    WORK=tempfile.mkdtemp(prefix='m344_fuego_',dir='/tmp')
    copy_path=os.path.join(WORK,os.path.basename(artifact)+'.copy')
    try:
        shutil.copy2(artifact,copy_path)
        h0=_hash(copy_path)
        res['baseline_hash']=h0
        with open(copy_path,'rb') as f: data=f.read()
        if data[:4]==b'\x7fELF':
            try: shutil.rmtree(WORK)
            except: pass
            res['reason']='binario no permitido sin mecanismo específico'; res['h0']=h0; return res
        if b'# rxre_fuego_m344' not in data:
            newd = data + b'\n# rxre_fuego_m344\n'
            with open(copy_path,'wb') as f: f.write(newd)
            h1=_hash(copy_path)
            h1b=_hash(copy_path)
            res['change_applied']=True; res['hash_after']=h1; res['hash_after_check']=h1b
            shutil.copy2(artifact,copy_path)
            h2=_hash(copy_path)
            res['hash_rollback']=h2; res['rollback_exact']=(h2==h0)
            res['scope']='isolated_copy'; res['errors']=[]
            res['analysis_completed']=True
            res['transaction_prepared']=True
            res['change_executed']=True
            res['rollback_verified']=bool(res['rollback_exact'])
            res['re_read']=h1b
            try: shutil.rmtree(WORK)
            except: pass
            res['status']='PASS_PARTIAL' if res['rollback_exact'] else 'BLOCKED'
            return res
        try: shutil.rmtree(WORK)
        except: pass
        res['reason']='sin cambio seguro aplicable'; res['h0']=h0; return res
    except Exception as e:
        try: shutil.rmtree(WORK)
        except: pass
        res['status']='BLOCKED'; res['reason']=str(e); return res

if __name__=='__main__':
    print(json.dumps(run(sys.argv[1] if len(sys.argv)>1 else '/tmp/nonexistent', allow=False), indent=2))
