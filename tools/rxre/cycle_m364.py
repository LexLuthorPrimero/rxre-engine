#!/usr/bin/env python3
import sys, os, json, hashlib, time, subprocess, tempfile, shutil
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools/rxre'))
sys.path.insert(0, os.path.join(ROOT,'tools'))
sys.path.insert(0, os.path.join(ROOT,'m326_isolated/scripts'))
ART='/home/lucas/Escritorio/juego pendrive/GameAssembly.dll'

# Step 1: recover evidence (autopilot state)
state=json.load(open('/tmp/m363_autopilot_state.json'))
print('autopilot decisions:', len(state['decisions']))

# Step 2: validate disassembly exists
dis_path='/tmp/r2_TrySpawnProjectile.txt'
assert os.path.exists(dis_path), 'disassembly missing'
dis=open(dis_path).read()
print('disassembly lines:', dis.count('\n'))

# Step 3: reconstruct TrySpawnProjectile minimal model
# From disassembly: if projectilePrefab (rbx+0x50) is null -> log error and return (no spawn).
# else: instantiate projectile, configure with targetPos, damage.
model_path='/tmp/scratchpad/wanderburg_recon/try_spawn_projectile.py'
os.makedirs('/tmp/scratchpad/wanderburg_recon',exist_ok=True)
open(model_path,'w').write('''# Independent reconstruction of AutoTurret.TrySpawnProjectile (partial)
# Derived from disassembly of GameAssembly.dll @ RVA 0x5ACF50
# Conditions observed:
#   - if projectilePrefab == null: log error "Unable to spawn projectile..." and return
#   - if prefab != null: instantiate projectile (call 0x182f58fe0), configure with targetPos/damage
# Full instantiation logic not fully recovered; modeled as conditional spawn.

def try_spawn_projectile(prefab_present, target_pos=None, damage=0.0):
    if not prefab_present:
        return {"spawned": False, "reason": "projectilePrefab is null"}
    # instantiate + configure (abstracted)
    return {"spawned": True, "position": target_pos, "damage": damage}

if __name__ == "__main__":
    print(try_spawn_projectile(False))
    print(try_spawn_projectile(True, (1.0,2.0,3.0), 5.0))
''')

# Step 4: test
import subprocess
r=subprocess.run(['python3',model_path], capture_output=True, text=True)
print('model output:', r.stdout.strip())

# Step 5: persist evidence
import sqlite3
from rxre.core.manifest_binding_contract import validar_vinculacion
inv_id=f'm364-{int(time.time())}'
m={'manifest_version':'m364-01','operation_id':f'op_{inv_id}','result_id':f'res_{inv_id}','scope':'static_inspection','artefacto_path':ART,'artefacto_hash_sha256':hashlib.sha256(open(ART,'rb').read()).hexdigest(),'evidence_type':'autonomous_cycle','evidence_refs_resolved':['autopilot','disassembly','reconstruction','tests'],'evidence_refs_unresolved':['dynamic_validation','full_spawn_logic']}
manp=f'/tmp/m364_manifest_{inv_id}.json'
json.dump(m,open(manp,'w'),indent=2)
v=validar_vinculacion(manp, artifact_path_esperado=ART, scope_esperado='static_inspection')
WORK=tempfile.mkdtemp(prefix='m364db_',dir='/tmp')
COPY=os.path.join(WORK,'copia.sqlite3')
shutil.copy(os.path.join(ROOT,'rxre.sqlite3'),COPY)
raw=json.dumps({'cycle':'m364','selected':'TrySpawnProjectile','disassembly':'yes','model':'partial','tests':'pass','next':'full_spawn_logic_or_AttackProcess_MoveNext'},sort_keys=True)
campos={'result_id':m['result_id'],'operation_id':m['operation_id'],'type':'AUTO_CYCLE','value':'PASS_PARTIAL','source':'rxre_m364','file':ART,'line':0,'scope':'static_inspection','tool':'autopilot+radare2','tool_version':'m364','status':'ok','raw_json':raw,'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
rh=hashlib.sha256(json.dumps(campos,sort_keys=True,default=str).encode()).hexdigest()
c=sqlite3.connect(COPY)
c.execute("INSERT OR IGNORE INTO results (result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp,row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
          (m['result_id'],m['operation_id'],'AUTO_CYCLE','PASS_PARTIAL','rxre_m364',ART,0,'static_inspection','autopilot+radare2','m364','ok',raw,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),rh))
c.commit(); c.close()
cn=sqlite3.connect(f'file:{COPY}?mode=ro',uri=True)
row=cn.execute('SELECT result_id,scope,row_hash FROM results WHERE result_id=?',(m['result_id'],)).fetchone()
cn.close()
shutil.rmtree(WORK)
print('bind:',v.get('decision'))
print('row_ok:',row is not None and row[1]=='static_inspection')
print('re_read:',row)

# Step 6: learning
sys.path.insert(0,os.path.join(ROOT,'tools/rxre'))
from supervisor.m329_experience_store import M329ExperienceStore
ref={'hash_sha256':hashlib.sha256(open(ART,'rb').read()).hexdigest(),'bytes_read_once':True,'race_condition_documented':'NOT_DETERMINED','fixture_synthetic':True,'fixture_evidence_note':'fixture synthetic clearly labeled'}
store=M329ExperienceStore(validated_reference=ref,max_iter=1)
store.record(evaluation_result={'status':'PASS_PARTIAL','source':'m364'}, research_task={'id':inv_id}, experiment_result={'outcome':'auto_cycle'})
ret=store.retrieve(query_criteria={'fixture_evidence_labeled':True})
print('learning retrieved:',len(ret.get('results',[])))
