#!/usr/bin/env python3
import sys, os, json, hashlib
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'m326_isolated/scripts'))
try:
    import m326_auth_verifier as av
except Exception as e:
    print(json.dumps({'status':'BLOCKED','reason':str(e)})); sys.exit(0)

res = {'check':'fuego_provision_m345', 'store_exists': os.path.exists('/tmp/rxre_auth_provisioned/identities.json'), 
       'svc_exists': os.path.exists('/tmp/rxre_306_work/servicio.key')}
if not res['store_exists'] or not res['svc_exists']:
    res['status']='BLOCKED'
    res['exact_admin_step']='tools/rxre/admin/provision_trust.py --provisioned-by <admin> --confirm --issuer-key <fuera_repo>/issuer.key --service-key <fuera_repo>/servicio.key (0600, uid/emisor/ejecutor provistos, identities.json con issuers/executors, key_sha256, nonces, firma válida)'
    res['requirements']=['issuer-key fuera repo','service-key fuera repo','identities.json fuera repo','permisos 0600','uid coincidente','nonce único','firma válida']
    print(json.dumps(res,indent=2)); sys.exit(0)
try:
    with open('/tmp/rxre_auth_provisioned/identities.json') as f:
        st=json.load(f)
    res['store_ok']=True
    res['issuers']=list(st.get('issuers',{}).keys())
    res['executors']=list(st.get('executors',{}).keys())
    res['status']='READY'
    res['note']='provisión presente; validación operacional requiere firma con clave del emisor'
    print(json.dumps(res,indent=2))
except Exception as e:
    res['status']='BLOCKED'; res['reason']=str(e); print(json.dumps(res,indent=2))
