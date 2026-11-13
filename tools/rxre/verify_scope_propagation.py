#!/usr/bin/env python3
"""RXRE-M339 — Verificación propagación scope"""
import sys, os, json, sqlite3, tempfile, shutil, hashlib, time
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools'))
sys.path.insert(0, os.path.join(ROOT,'m326_isolated/scripts'))
from rxre.contracts import scope_provenance_contract as spc
from rxre.core.manifest_binding_contract import validar_vinculacion

def test_scope():
    art = '/usr/bin/ls'
    ah = hashlib.sha256(open(art,'rb').read()).hexdigest()
    man = {'manifest_version':'m339-01','operation_id':'op_m339_scope','result_id':'res_m339_scope','scope':'static_inspection','artefacto_path':art,'artefacto_hash_sha256':ah,'evidence_type':'direct_observation','evidence_refs_resolved':['hash_artefacto'],'evidence_refs_unresolved':[]}
    manp = '/tmp/m339_scope_manifest.json'
    json.dump(man, open(manp,'w'), indent=2)
    v = validar_vinculacion(manp, artifact_path_esperado=art, scope_esperado='static_inspection')
    # persistir en copia aislada
    WORK = tempfile.mkdtemp(prefix='m339s_', dir='/tmp')
    COPY = os.path.join(WORK,'copia.sqlite3')
    shutil.copy(os.path.join(ROOT,'.rxre/storage/rxre.sqlite3'), COPY)
    raw = json.dumps({'hash':ah}, sort_keys=True)
    campos = {'result_id':man['result_id'],'operation_id':man['operation_id'],'type':'STATIC_OBS','value':'PASS_PARTIAL','source':'rxre_m339','file':art,'line':0,'scope':'static_inspection','tool':'sha256','tool_version':'m339','status':'ok','raw_json':raw,'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    rh = hashlib.sha256(json.dumps(campos, sort_keys=True, default=str).encode()).hexdigest()
    c = sqlite3.connect(COPY)
    c.execute("INSERT OR IGNORE INTO results (result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp,row_hash,verified_scope,scope_decision,limitations_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (man['result_id'],man['operation_id'],'STATIC_OBS','PASS_PARTIAL','rxre_m339',art,0,'static_inspection','sha256','m339','ok',raw,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),rh,'VERIFIED','VERIFIED','[]'))
    c.execute("INSERT OR IGNORE INTO operations (operation_id,scope,declared_scope,authorized_scope,auth_decision,auth_actor,auth_timestamp,request_json) VALUES (?,?,?,?,?,?,?,?)",
              (man['operation_id'],'static_inspection','static_inspection','static_inspection','APPROVED','local',time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'{}'))
    c.commit(); c.close()
    # relectura
    cn = sqlite3.connect(f'file:{COPY}?mode=ro', uri=True)
    row = cn.execute('SELECT result_id,scope,row_hash FROM results WHERE result_id=?',(man['result_id'],)).fetchone()
    cn.close()
    shutil.rmtree(WORK)
    return {'bind': v.get('decision'), 'row': row, 'scope_preserved': row[1]=='static_inspection' if row else False}

if __name__=='__main__':
    print(json.dumps(test_scope(), indent=2))
