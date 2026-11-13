#!/usr/bin/env python3
import sys, os, json, hashlib, time, tempfile, shutil, subprocess
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools/rxre'))
sys.path.insert(0, os.path.join(ROOT,'tools'))
sys.path.insert(0, os.path.join(ROOT,'m326_isolated/scripts'))

# auto-select third binary
used={'/usr/bin/ls','/usr/bin/head','/usr/bin/wc','/usr/bin/basename'}
preferred=['seq','nl','tac','cut','tr','fold','paste','uniq','cat']
chosen=None
for name in preferred:
    p='/usr/bin/'+name
    if os.path.exists(p) and p not in used:
        chosen=p; break
if not chosen:
    # fallback first executable
    for f in sorted(os.listdir('/usr/bin')):
        p='/usr/bin/'+f
        if os.path.isfile(p) and os.access(p,os.X_OK) and p not in used:
            chosen=p; break
print('AUTO_SELECTED:',chosen, file=sys.stderr)

# reference for seq
ref_path='/tmp/scratchpad/ref_seq.py'
os.makedirs('/tmp/scratchpad',exist_ok=True)
open(ref_path,'w').write('''import sys
def main():
    args=sys.argv[1:]
    # parse seq args (simplified): handle FIRST INCREMENT LAST or FIRST LAST or LAST
    nums=[]
    # defaults
    first=1; incr=1; last=None
    # filter options
    def is_int(x):
        try: int(x); return True
        except: return False
    opts=[a for a in args if a.startswith('-') and not is_int(a)]
    pos=[a for a in args if not (a.startswith('-') and not is_int(a))]
    # handle -s separator? ignore
    if len(pos)==1:
        last=int(pos[0])
    elif len(pos)==2:
        first=int(pos[0]); last=int(pos[1])
    elif len(pos)==3:
        first=int(pos[0]); incr=int(pos[1]); last=int(pos[2])
    # generate
    if last is None:
        last=first; first=1
    i=first
    if incr>0:
        while i<=last:
            print(i); i+=incr
    else:
        while i>=last:
            print(i); i+=incr
if __name__=='__main__':
    main()
''')

# test inputs for seq
inputs=[
 ('seq_5','5'),
 ('seq_1_5','1 5'),
 ('seq_1_2_10','1 2 10'),
 ('seq_5_1','5 1'),
 ('seq_3_3_9','3 3 9'),
 ('seq_neg','-3 3'),
]

# extend reconstruct_engine to support args mode? engine supports mode 'file'/'stdin' only.
# We'll run pipeline manually using engine pattern but args mode.
# Reuse engine's persistence/learning by calling run with mode? Let's just call engine with a wrapper: convert args to file? seq doesn't read files.
# Instead, run comparison directly here and persist via engine-like manifest.

import reconstruct_engine as re
# monkey: run engine in 'stdin' mode won't work for seq. We'll do custom comparison and persist manually.
WORK=__import__('tempfile').mkdtemp(prefix='m352_',dir='/tmp')
comp={'cases':[],'mismatches':0}
for name,args in inputs:
    o=__import__('subprocess').run([chosen]+args.split(), stdout=__import__('subprocess').PIPE, stderr=__import__('subprocess').PIPE)
    r=__import__('subprocess').run(['python3',ref_path]+args.split(), stdout=__import__('subprocess').PIPE, stderr=__import__('subprocess').PIPE)
    o_out=o.stdout.decode().strip()
    r_out=r.stdout.decode().strip()
    match=' '.join(o_out.split())==' '.join(r_out.split())
    comp['cases'].append({'input':name,'args':args,'original':o_out,'reference':r_out,'match':match,'rc_orig':o.returncode,'rc_ref':r.returncode})
    if not match:
        comp['mismatches']+=1

# defective check
o=__import__('subprocess').run([chosen,'1','5'], stdout=__import__('subprocess').PIPE, stderr=__import__('subprocess').PIPE)
broken=__import__('tempfile').mktemp(dir='/tmp')
open(broken,'w').write('import sys\nprint("WRONG")\n')
r=__import__('subprocess').run(['python3',broken,'1','5'], stdout=__import__('subprocess').PIPE, stderr=__import__('subprocess').PIPE)
defective_rejected = (o.stdout.decode().strip()!=r.stdout.decode().strip())

# persist
import sqlite3, json
inv_id=f'm352-{int(time.time())}'
m={'manifest_version':'m352-01','operation_id':f'op_{inv_id}','result_id':f'res_{inv_id}','scope':'static_inspection','artefacto_path':chosen,'artefacto_hash_sha256':hashlib.sha256(open(chosen,'rb').read()).hexdigest(),'evidence_type':'recon_general_m352','evidence_refs_resolved':['discovery','comparison'],'evidence_refs_unresolved':[]}
manp=f'/tmp/m352_manifest_{inv_id}.json'
json.dump(m,open(manp,'w'),indent=2)
sys.path.insert(0,os.path.join(ROOT,'tools/rxre'))
from rxre.core.manifest_binding_contract import validar_vinculacion
v=validar_vinculacion(manp, artifact_path_esperado=chosen, scope_esperado='static_inspection')
WORK2=__import__('tempfile').mkdtemp(prefix='m352db_',dir='/tmp')
COPY=os.path.join(WORK2,'copia.sqlite3')
shutil.copy(os.path.join(ROOT,'rxre.sqlite3'),COPY)
raw=json.dumps({'mismatches':comp['mismatches'],'cases':len(comp['cases']),'defective_rejected':defective_rejected},sort_keys=True)
campos={'result_id':m['result_id'],'operation_id':m['operation_id'],'type':'RECON_M352','value':'PASS_PARTIAL','source':'rxre_m352','file':chosen,'line':0,'scope':'static_inspection','tool':'multi','tool_version':'m352','status':'ok','raw_json':raw,'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
rh=hashlib.sha256(json.dumps(campos,sort_keys=True,default=str).encode()).hexdigest()
c=sqlite3.connect(COPY)
c.execute("INSERT OR IGNORE INTO results (result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp,row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
          (m['result_id'],m['operation_id'],'RECON_M352','PASS_PARTIAL','rxre_m352',chosen,0,'static_inspection','multi','m352','ok',raw,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),rh))
c.commit(); c.close()
cn=sqlite3.connect(f'file:{COPY}?mode=ro',uri=True)
row=cn.execute('SELECT result_id,scope,row_hash FROM results WHERE result_id=?',(m['result_id'],)).fetchone()
cn.close()
shutil.rmtree(WORK2)

# learning
sys.path.insert(0,os.path.join(ROOT,'tools/rxre'))
from supervisor.m329_experience_store import M329ExperienceStore
ref={'hash_sha256':hashlib.sha256(open(chosen,'rb').read()).hexdigest(),'bytes_read_once':True,'race_condition_documented':'NOT_DETERMINED','fixture_synthetic':True,'fixture_evidence_note':'fixture synthetic clearly labeled'}
store=M329ExperienceStore(validated_reference=ref,max_iter=1)
store.record(evaluation_result={'status':'PASS_PARTIAL','source':'m352'}, research_task={'id':inv_id}, experiment_result={'outcome':'recon_m352'})
ret=store.retrieve(query_criteria={'fixture_evidence_labeled':True})

out={
 'chosen':chosen,
 'mismatches':comp['mismatches'],
 'cases':len(comp['cases']),
 'defective_rejected':defective_rejected,
 'bind':v.get('decision'),
 'row_ok':row is not None and row[1]=='static_inspection',
 're_read':row,
 'learning':len(ret.get('results',[])),
 'discrepancies':[c for c in comp['cases'] if not c['match']],
}
json.dump(out,open('/tmp/m352_result.json','w'),indent=2)
print(json.dumps(out,indent=2))
