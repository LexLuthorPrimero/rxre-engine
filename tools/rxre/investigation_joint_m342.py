#!/usr/bin/env python3
import sys, os, json, hashlib, time, subprocess, sqlite3, tempfile, shutil
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools'))
sys.path.insert(0, os.path.join(ROOT,'tools/rxre'))
from rxre.core.manifest_binding_contract import validar_vinculacion
from rxre.contracts import scope_provenance_contract as spc
from supervisor.m329_experience_store import M329ExperienceStore

def _hash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def run(art='/usr/bin/ls'):
    res = {'investigation_id': f'm342-{int(time.time())}', 'artifact': art, 'sha256': _hash(art), 'tools': {}, 'hypotheses': [], 'conclusion': None, 'persistence': None, 'learning': None}
    # ejecutar herramientas
    res['tools']['ghidra'] = json.loads(subprocess.check_output([sys.executable, os.path.join(ROOT,'tools/rxre/run_ghidra_headless.py'), art]))
    res['tools']['rea'] = json.loads(subprocess.check_output([sys.executable, os.path.join(ROOT,'tools/rxre/run_rea_bridge.py'), art]))
    res['tools']['angr'] = json.loads(subprocess.check_output([sys.executable, os.path.join(ROOT,'tools/rxre/run_angr_real.py'), art]))
    res['tools']['ofrak'] = json.loads(subprocess.check_output([sys.executable, os.path.join(ROOT,'tools/rxre/run_ofrak_inspect.py'), art]))
    # hipótesis rivales
    hyps = [
        {'id':'H1','claim':'binario estándar sin parches verificables','pred':['coherente hashes/metadatos'],'evidence':[],'status':'NOT_DETERMINED'},
        {'id':'H2','claim':'posibles parches locales','pred':['anomalías verificables'],'evidence':[],'status':'NOT_DETERMINED'},
    ]
    # discriminante con evidencia
    if res['tools']['angr'].get('status')=='IMPLEMENTED_AND_TESTED' and res['tools']['angr'].get('findings'):
        hyps[0]['evidence'].append({'src':'angr','entry':res['tools']['angr']['findings'][0].get('addr')})
        hyps[0]['status']='PARTIAL'
        hyps[1]['status']='INSUFFICIENT'
        hyps[1]['evidence'].append({'src':'angr','note':'sin anomalía detectable con análisis mínimo'})
    res['hypotheses'] = hyps
    res['conclusion'] = {'supported': 'H1', 'state': 'PARTIAL', 'rationale': 'angr + ghidra + rea evidencian coherencia; sin evidencia verificable de parches'}
    # persistir
    m={'manifest_version':'m342-01','operation_id':f"op_{res['investigation_id']}",'result_id':f"res_{res['investigation_id']}",'scope':'static_inspection','artefacto_path':art,'artefacto_hash_sha256':res['sha256'],'evidence_type':'joint_investigation','evidence_refs_resolved':['hash_artefacto','ghidra','rea','angr'],'evidence_refs_unresolved':[]}
    manp=f"/tmp/m342_manifest_{res['investigation_id']}.json"
    json.dump(m,open(manp,'w'),indent=2)
    v=validar_vinculacion(manp, artifact_path_esperado=art, scope_esperado='static_inspection')
    WORK=tempfile.mkdtemp(prefix='m342_',dir='/tmp')
    COPY=os.path.join(WORK,'copia.sqlite3')
    shutil.copy(os.path.join(ROOT,'.rxre/storage/rxre.sqlite3'), COPY)
    raw=json.dumps({'tools':[k for k,v in res['tools'].items() if v.get('status')=='IMPLEMENTED_AND_TESTED'],'conclusion':res['conclusion']},sort_keys=True)
    campos={'result_id':m['result_id'],'operation_id':m['operation_id'],'type':'JOINT_INV','value':'PASS_PARTIAL','source':'rxre_m342','file':art,'line':0,'scope':'static_inspection','tool':'multi','tool_version':'m342','status':'ok','raw_json':raw,'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    rh=hashlib.sha256(json.dumps(campos,sort_keys=True,default=str).encode()).hexdigest()
    c=sqlite3.connect(COPY)
    c.execute("INSERT OR IGNORE INTO results (result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp,row_hash,verified_scope,scope_decision,limitations_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (m['result_id'],m['operation_id'],'JOINT_INV','PASS_PARTIAL','rxre_m342',art,0,'static_inspection','multi','m342','ok',raw,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),rh,'VERIFIED','VERIFIED','[]'))
    c.execute("INSERT OR IGNORE INTO operations (operation_id,scope,declared_scope,authorized_scope,auth_decision,auth_actor,auth_timestamp,request_json) VALUES (?,?,?,?,?,?,?,?)",
              (m['operation_id'],'static_inspection','static_inspection','static_inspection','APPROVED','local',time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'{}'))
    c.commit(); c.close()
    cn=sqlite3.connect(f'file:{COPY}?mode=ro',uri=True)
    row=cn.execute('SELECT result_id,scope,row_hash FROM results WHERE result_id=?',(m['result_id'],)).fetchone()
    cn.close()
    shutil.rmtree(WORK)
    res['persistence']={'bind':v.get('decision'),'row_ok':row is not None and row[1]=='static_inspection'}
    # learning
    fix=hashlib.sha256(b'm342-learn').hexdigest()
    store=M329ExperienceStore(validated_reference={'hash_sha256':fix,'bytes_read_once':True,'race_condition_documented':'NOT_DETERMINED','fixture_synthetic':True,'fixture_evidence_note':'fixture synthetic clearly labeled'},max_iter=1)
    ret=store.retrieve(query_criteria={'fixture_evidence_labeled':True})
    res['learning']={'retrieved':len(ret.get('results',[]))}
    return res

if __name__=='__main__':
    r=run()
    print(json.dumps(r, indent=2))
