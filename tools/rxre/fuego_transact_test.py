#!/usr/bin/env python3
import sys, os, json, hashlib, tempfile, shutil, time
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools'))
sys.path.insert(0, os.path.join(ROOT,'m326_isolated/scripts'))
import m326_auth_verifier as av

def _hash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def test():
    res = {'phase':'FUEGO_TEST','provision_present': os.path.exists('/tmp/rxre_auth_provisioned/identities.json'), 'svc_present': os.path.exists('/tmp/rxre_306_work/servicio.key'), 'status':'BLOCKED'}
    if not res['provision_present'] or not res['svc_present']:
        res['reason'] = 'provisión persistente legítima ausente'
        res['required'] = 'tools/rxre/admin/provision_trust.py --provisioned-by <admin> --confirm --issuer-key <fuera_repo>/issuer.key --service-key <fuera_repo>/servicio.key con permisos 0600, uid coincidente, identities.json válido'
        return res
    # si existiera, seguiría flujo aislado
    res['status']='READY'
    return res

if __name__=='__main__':
    print(json.dumps(test(), indent=2))
