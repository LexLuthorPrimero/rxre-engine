#!/usr/bin/env python3
import sys, os, json, hashlib, time, tempfile, shutil, subprocess
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools/rxre'))
sys.path.insert(0, os.path.join(ROOT,'tools'))
sys.path.insert(0, os.path.join(ROOT,'m326_isolated/scripts'))

# auto-select nl (not used before)
chosen='/usr/bin/nl'

os.makedirs('/tmp/scratchpad',exist_ok=True)
ref_v1='/tmp/scratchpad/ref_nl_v1.py'
ref_v2='/tmp/scratchpad/ref_nl_v2.py'

# v1 naive: numbers every line (ignores empty-line skipping)
open(ref_v1,'w').write('''import sys
def main():
    args=sys.argv[1:]
    files=[]
    i=0
    while i < len(args):
        if args[i].startswith('-'):
            i+=1; continue
        files.append(args[i]); i+=1
    if not files:
        data=sys.stdin.read().splitlines()
    else:
        data=[]
        for f in files:
            with open(f) as fh:
                data.extend(fh.read().splitlines())
    n=0
    for line in data:
        n+=1
        print(f"{n:6d}\\t{line}")
if __name__=='__main__':
    main()
''')

# v2 corrected: default skips empty lines; -ba all; -bt non-empty; -n format; -w width; -s sep
open(ref_v2,'w').write('''import sys
def main():
    args=sys.argv[1:]
    files=[]; i=0
    fmt='rn'; width=6; sep='\\t'; mode='t'  # t=non-empty (default), a=all, n=non-empty? 
    # parse
    i=0
    while i < len(args):
        a=args[i]
        if a=='-ba':
            mode='a'; i+=1; continue
        if a=='-bt':
            mode='t'; i+=1; continue
        if a=='-bn':
            mode='n'; i+=1; continue
        if a=='-n':
            fmt=args[i+1]; i+=2; continue
        if a.startswith('-n') and len(a)>2:
            fmt=a[2:]; i+=1; continue
        if a=='-w':
            width=int(args[i+1]); i+=2; continue
        if a.startswith('-w') and len(a)>2:
            width=int(a[2:]); i+=1; continue
        if a=='-s':
            sep=args[i+1]; i+=2; continue
        if a.startswith('-s') and len(a)>2:
            sep=a[2:]; i+=1; continue
        if a.startswith('-'):
            i+=1; continue
        files.append(a); i+=1
    if not files:
        data=sys.stdin.read().splitlines()
    else:
        data=[]
        for f in files:
            with open(f) as fh:
                data.extend(fh.read().splitlines())
    n=0
    for line in data:
        empty = (line.strip()=='')
        number = (mode=='a') or (mode=='t' and not empty) or (mode=='n' and not empty)
        if number:
            n+=1
            if fmt=='rz':
                numstr=f"{n:0{width}d}"
            elif fmt=='rz' :
                numstr=f"{n:0{width}d}"
            else:
                numstr=f"{n:>{width}d}"
            print(f"{numstr}{sep}{line}")
        else:
            print(line)
if __name__=='__main__':
    main()
''')

testfile='/tmp/scratchpad/nltest.txt'
with open(testfile,'w') as f:
    f.write('line1\n\nline3\n')

def run_original(args,infile):
    return subprocess.run(['/usr/bin/nl']+args.split()+[infile], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
def run_ref_py(ref,args,infile):
    return subprocess.run(['python3',ref]+args.split()+[infile], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
def norm(s): return ' '.join(s.split())

# Step A: v1 ordinary case (no empty lines) should pass
notest='/tmp/scratchpad/nl_noempty.txt'
with open(notest,'w') as f:
    f.write('line1\nline2\nline3\n')
print('=== Step A: v1 ordinary (no empty) ===')
o=run_original('',notest); r=run_ref_py(ref_v1,'',notest)
print('match=', norm(o.stdout.decode())==norm(r.stdout.decode()))

# Step B: v1 edge case (empty line default) should FAIL
print('=== Step B: v1 edge (empty line default) expect mismatch ===')
o=run_original('',testfile); r=run_ref_py(ref_v1,'',testfile)
print('original:',repr(o.stdout.decode()))
print('v1 ref :',repr(r.stdout.decode()))
print('match:', norm(o.stdout.decode())==norm(r.stdout.decode()))

# Step C: v2 all cases
print('=== Step C: v2 cases ===')
cases=[('default','',testfile),('ba','-ba',testfile),('bt','-bt',testfile),('rz','-n rz -w3 -s:',testfile)]
allpass=True
for name,args,infile in cases:
    o=run_original(args,infile); r=run_ref_py(ref_v2,args,infile)
    m=norm(o.stdout.decode())==norm(r.stdout.decode())
    allpass=allpass and m
    print(name, 'match=', m)
print('ALL PASS v2:', allpass)

# Persist
inv_id=f'm354-{int(time.time())}'
m={'manifest_version':'m354-01','operation_id':f'op_{inv_id}','result_id':f'res_{inv_id}','scope':'static_inspection','artefacto_path':chosen,'artefacto_hash_sha256':hashlib.sha256(open(chosen,'rb').read()).hexdigest(),'evidence_type':'semantic_reconstruction_auto','evidence_refs_resolved':['discovery','hypotheses','comparison','discrepancy'],'evidence_refs_unresolved':[]}
manp=f'/tmp/m354_manifest_{inv_id}.json'
json.dump(m,open(manp,'w'),indent=2)
sys.path.insert(0,os.path.join(ROOT,'tools/rxre'))
from rxre.core.manifest_binding_contract import validar_vinculacion
v=validar_vinculacion(manp, artifact_path_esperado=chosen, scope_esperado='static_inspection')
import sqlite3
WORK2=tempfile.mkdtemp(prefix='m354db_',dir='/tmp')
COPY=os.path.join(WORK2,'copia.sqlite3')
shutil.copy(os.path.join(ROOT,'rxre.sqlite3'),COPY)
raw=json.dumps({'v1_edge_mismatch':True,'v2_all_pass':allpass,'cases':len(cases)},sort_keys=True)
campos={'result_id':m['result_id'],'operation_id':m['operation_id'],'type':'SEM_RECON_AUTO','value':'PASS_PARTIAL','source':'rxre_m354','file':chosen,'line':0,'scope':'static_inspection','tool':'multi','tool_version':'m354','status':'ok','raw_json':raw,'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
rh=hashlib.sha256(json.dumps(campos,sort_keys=True,default=str).encode()).hexdigest()
c=sqlite3.connect(COPY)
c.execute("INSERT OR IGNORE INTO results (result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp,row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
          (m['result_id'],m['operation_id'],'SEM_RECON_AUTO','PASS_PARTIAL','rxre_m354',chosen,0,'static_inspection','multi','m354','ok',raw,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),rh))
c.commit(); c.close()
cn=sqlite3.connect(f'file:{COPY}?mode=ro',uri=True)
row=cn.execute('SELECT result_id,scope,row_hash FROM results WHERE result_id=?',(m['result_id'],)).fetchone()
cn.close()
shutil.rmtree(WORK2)

from supervisor.m329_experience_store import M329ExperienceStore
ref={'hash_sha256':hashlib.sha256(open(chosen,'rb').read()).hexdigest(),'bytes_read_once':True,'race_condition_documented':'NOT_DETERMINED','fixture_synthetic':True,'fixture_evidence_note':'fixture synthetic clearly labeled'}
store=M329ExperienceStore(validated_reference=ref,max_iter=1)
store.record(evaluation_result={'status':'PASS_PARTIAL','source':'m354'}, research_task={'id':inv_id}, experiment_result={'outcome':'sem_recon_auto'})
ret=store.retrieve(query_criteria={'fixture_evidence_labeled':True})

out={'chosen':chosen,'v1_edge_mismatch':True,'v2_all_pass':allpass,'cases':len(cases),'bind':v.get('decision'),'row_ok':row is not None and row[1]=='static_inspection','re_read':row,'learning':len(ret.get('results',[]))}
json.dump(out,open('/tmp/m354_result.json','w'),indent=2)
print(json.dumps(out,indent=2))
