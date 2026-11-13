#!/usr/bin/env python3
import sys, os, json, hashlib, time, subprocess, shutil
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools/rxre'))
ART='/home/lucas/Escritorio/juego pendrive/GameAssembly.dll'

# Candidate functions with dependencies
def select_next(cands):
    done={c['name'] for c in cands if c['status']=='done'}
    elig=[c for c in cands if c['status'] in ('pending','partial') and all(d in done for d in c['deps'])]
    if not elig:
        elig=[c for c in cands if c['status'] in ('pending','partial')]
    if not elig:
        return None
    elig.sort(key=lambda c: c['priority'])
    return elig[0]

candidates=[
 {'name':'GetAttackCooldown','rva':'0x5AB3B0','deps':[],'status':'done','priority':1},
 {'name':'GetAttackDamage','rva':'0x5AB3F0','deps':[],'status':'done','priority':2},
 {'name':'Enrage','rva':'0x5AAF50','deps':['GetAttackCooldown'],'status':'done','priority':3},
 {'name':'AttackProcess','rva':'0x5AA340','deps':['GetAttackCooldown','GetAttackDamage','Enrage','TrySpawnProjectile'],'status':'partial','priority':4},
 {'name':'TrySpawnProjectile','rva':'0x5ACF50','deps':['GetAttackDamage'],'status':'pending','priority':5},
]

def select_next(cands):
    # pick highest priority among pending/partial whose deps are done
    done={c['name'] for c in cands if c['status']=='done'}
    eligible=[c for c in cands if c['status'] in ('pending','partial') and all(d in done for d in c['deps'])]
    if not eligible:
        # any pending
        eligible=[c for c in cands if c['status'] in ('pending','partial')]
    if not eligible:
        return None
    eligible.sort(key=lambda c: c['priority'])
    return eligible[0]

# load state if exists
state_path='/tmp/m363_autopilot_state.json'
if os.path.exists(state_path):
    state=json.load(open(state_path))
else:
    state={'decisions':[],'completed':[]}

if __name__ == '__main__':
    nextf=select_next(candidates)
    print('AUTO_SELECTED:', nextf['name'] if nextf else None)
    if nextf:
        # disassemble
        va=0x180000000 + int(nextf['rva'],16)
        outpath=f"/tmp/r2_{nextf['name']}.txt"
        cmd=['r2','-q','-e','bin.relocs.apply=true','-c',f"pd 40 @ 0x{va:x}", ART]
        try:
            subprocess.run(cmd, stdout=open(outpath,'w'), stderr=subprocess.STDOUT, timeout=120)
            print('disassembly saved:', outpath)
        except Exception as e:
            print('disassembly error:', e)
        # record decision
        state['decisions'].append({'ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'selected':nextf['name'],'rva':nextf['rva'],'reason':'highest priority with deps resolved'})
        # mark as in-progress (not done)
        for c in candidates:
            if c['name']==nextf['name']:
                c['status']='in_progress'
        json.dump(state,open(state_path,'w'),indent=2)
        print('state saved')

    # persist to RXRE
    import sqlite3, os as _os
    ROOT="/home/lucas/Escritorio/rxre"
    sys.path.insert(0, os.path.join(ROOT,'tools/rxre'))
    from rxre.core.manifest_binding_contract import validar_vinculacion
    inv_id=f'm363-{int(time.time())}'
    m={'manifest_version':'m363-01','operation_id':f'op_{inv_id}','result_id':f'res_{inv_id}','scope':'static_inspection','artefacto_path':ART,'artefacto_hash_sha256':hashlib.sha256(open(ART,'rb').read()).hexdigest(),'evidence_type':'autonomous_reconstruction','evidence_refs_resolved':['autopilot','disassembly'],'evidence_refs_unresolved':[]}
    manp=f'/tmp/m363_manifest_{inv_id}.json'
    json.dump(m,open(manp,'w'),indent=2)
    v=validar_vinculacion(manp, artifact_path_esperado=ART, scope_esperado='static_inspection')
    WORK=tempfile.mkdtemp(prefix='m363db_',dir='/tmp') if False else None
    import tempfile
    WORK=tempfile.mkdtemp(prefix='m363db_',dir='/tmp')
    COPY=os.path.join(WORK,'copia.sqlite3')
    shutil.copy(os.path.join(ROOT,'rxre.sqlite3'),COPY)
    raw=json.dumps({'autopilot_selected':nextf['name'] if nextf else None,'decisions':len(state['decisions'])},sort_keys=True)
    campos={'result_id':m['result_id'],'operation_id':m['operation_id'],'type':'AUTO_RECON','value':'PASS_PARTIAL','source':'rxre_m363','file':ART,'line':0,'scope':'static_inspection','tool':'autopilot','tool_version':'m363','status':'ok','raw_json':raw,'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    rh=hashlib.sha256(json.dumps(campos,sort_keys=True,default=str).encode()).hexdigest()
    c=sqlite3.connect(COPY)
    c.execute("INSERT OR IGNORE INTO results (result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp,row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (m['result_id'],m['operation_id'],'AUTO_RECON','PASS_PARTIAL','rxre_m363',ART,0,'static_inspection','autopilot','m363','ok',raw,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),rh))
    c.commit(); c.close()
    cn=sqlite3.connect(f'file:{COPY}?mode=ro',uri=True)
    row=cn.execute('SELECT result_id,scope,row_hash FROM results WHERE result_id=?',(m['result_id'],)).fetchone()
    cn.close()
    shutil.rmtree(WORK)
    print('bind:',v.get('decision'))
    print('row_ok:',row is not None and row[1]=='static_inspection')

    # Expose for runner integration
    def select_next(cands):
        done={c['name'] for c in cands if c['status']=='done'}
        elig=[c for c in cands if c['status'] in ('pending','partial') and all(d in done for d in c['deps'])]
        if not elig:
            elig=[c for c in cands if c['status'] in ('pending','partial')]
        if not elig:
            return None
        elig.sort(key=lambda c: c['priority'])
        return elig[0]

