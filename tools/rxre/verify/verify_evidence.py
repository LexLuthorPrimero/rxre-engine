#!/usr/bin/env python3
import sys, json, hashlib, sqlite3, os
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools'))
sys.path.insert(0, os.path.join(ROOT,'m326_isolated/scripts'))
from rxre.contracts import scope_provenance_contract as spc
from rxre.core.manifest_binding_contract import validar_vinculacion

def verify(manifest_path, artifact_path, scope='static_inspection'):
    res = {'manifest_bind': None, 'scope_ver': None, 'hash_ok': None}
    # hash
    h = hashlib.sha256(open(artifact_path,'rb').read()).hexdigest()
    res['hash_artifact'] = h
    # bind
    res['manifest_bind'] = validar_vinculacion(manifest_path, artifact_path_esperado=artifact_path, scope_esperado=scope)
    # scope
    res['scope_ver'] = spc.verificar_autoridad_scope(evidence_ref='ref_verify', claim_scope=scope, db_op_path=os.path.join(ROOT,'.rxre/storage/rxre.sqlite3'), db_op_result_id='res_dummy', manifest_e2e_path=manifest_path, observed_artifact_path=artifact_path, observed_hash=h)
    return res

if __name__=='__main__':
    print(json.dumps(verify(sys.argv[1], sys.argv[2]), indent=2))
